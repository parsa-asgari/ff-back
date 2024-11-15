
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse


router = APIRouter()



@router.get("/")
async def base(request: Request):
    return JSONResponse({"alive": True})