import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "belok.api.app:create_app",
        factory=True,
        host="0.0.0.0",  # noqa: S104
        port=8000,
        proxy_headers=True,
        forwarded_allow_ips="*",
    )
