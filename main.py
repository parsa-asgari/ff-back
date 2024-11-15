if __name__ == "__main__":
    import uvicorn

    uvicorn.run("Finda:app", reload=False, port=8992, host="0.0.0.0",workers=8)
