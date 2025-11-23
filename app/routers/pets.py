from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from uuid import uuid4
from pathlib import Path
from ..db import get_db
from ..config import get_settings
from ..security import get_current_user
from ..schemas.pet import PetCreate, PetOut

router = APIRouter()
settings = get_settings()

def to_out(doc: dict) -> dict:
    doc = dict(doc)
    doc["id"] = str(doc.pop("_id"))
    if "photos" not in doc:
        doc["photos"] = []
    return doc

@router.get("", response_model=list[PetOut])
async def list_pets(db: AsyncIOMotorDatabase = Depends(get_db)):
    docs = await db.pets.find().to_list(500)
    return [to_out(d) for d in docs]

@router.get("/my", response_model=list[PetOut])
async def my_pets(
    current=Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    docs = await db.pets.find({"owner_id": current["id"]}).to_list(200)
    return [to_out(d) for d in docs]

@router.post("", response_model=PetOut, status_code=status.HTTP_201_CREATED)
async def create_pet(
    payload: PetCreate,
    current=Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    doc = payload.model_dump()
    doc["owner_id"] = current["id"]     # lo pone el backend
    doc.setdefault("photos", [])
    res = await db.pets.insert_one(doc)
    doc["_id"] = res.inserted_id
    return to_out(doc)

@router.post("/{pet_id}/photos", response_model=PetOut, status_code=status.HTTP_201_CREATED)
async def upload_pet_photo(
    pet_id: str,
    file: UploadFile = File(...),
    current=Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    # valida pet + ownership
    try:
        oid = ObjectId(pet_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Mascota no encontrada")
    pet = await db.pets.find_one({"_id": oid})
    if not pet:
        raise HTTPException(status_code=404, detail="Mascota no encontrada")
    if str(pet.get("owner_id")) != current["id"]:
        raise HTTPException(status_code=403, detail="No eres el propietario")

    # valida tipo/size básico
    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(status_code=415, detail="Solo imágenes")

    ext = Path(file.filename or "").suffix.lower() or ".jpg"
    filename = f"{uuid4().hex}{ext}"
    rel_path = Path("pets") / filename
    abs_path = Path(settings.media_dir) / rel_path

    # guarda async
    import aiofiles
    async with aiofiles.open(abs_path, "wb") as out:
        while chunk := await file.read(1024 * 1024):
            await out.write(chunk)

    url = f"/media/{rel_path.as_posix()}"
    await db.pets.update_one({"_id": oid}, {"$push": {"photos": url}})
    pet = await db.pets.find_one({"_id": oid})
    return to_out(pet)

@router.delete("/{pet_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_pet(
    pet_id: str,
    current=Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    try:
        oid = ObjectId(pet_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Mascota no encontrada")

    result = await db.pets.delete_one({"_id": oid, "owner_id": current["id"]})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Mascota no encontrada")
    return None

@router.delete("/{pet_id}/photos", response_model=PetOut)
async def delete_pet_photo(
    pet_id: str,
    url: str,  # pásala como query ?url=/media/pets/xxx.jpg
    current=Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    try:
        oid = ObjectId(pet_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Mascota no encontrada")
    pet = await db.pets.find_one({"_id": oid})
    if not pet:
        raise HTTPException(status_code=404, detail="Mascota no encontrada")
    if str(pet.get("owner_id")) != current["id"]:
        raise HTTPException(status_code=403, detail="No eres el propietario")

    await db.pets.update_one({"_id": oid}, {"$pull": {"photos": url}})

    # borra fichero en disco (best effort)
    try:
        from urllib.parse import urlparse
        p = urlparse(url).path  # "/media/pets/xxx.jpg"
        abs_path = Path(settings.media_dir) / Path(p).relative_to("/media")
        abs_path.unlink(missing_ok=True)
    except Exception:
        pass

    pet = await db.pets.find_one({"_id": oid})
    return to_out(pet)
