import json
from typing import Any

from aiobotocore.session import get_session


class S3MediaStorage:
    """S3-compatible storage (MinIO locally). Objects are served from `public_base_url`."""

    def __init__(
        self,
        endpoint_url: str,
        region: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        public_base_url: str,
    ) -> None:
        self._client_args: dict[str, Any] = {
            "endpoint_url": endpoint_url,
            "region_name": region,
            "aws_access_key_id": access_key,
            "aws_secret_access_key": secret_key,
        }
        self._bucket = bucket
        self._public_base_url = public_base_url.rstrip("/")
        self._session = get_session()

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        async with self._session.create_client("s3", **self._client_args) as client:
            await client.put_object(
                Bucket=self._bucket,
                Key=key,
                Body=data,
                ContentType=content_type,
                CacheControl="public, max-age=31536000, immutable",
            )

    async def delete(self, key: str) -> None:
        async with self._session.create_client("s3", **self._client_args) as client:
            await client.delete_object(Bucket=self._bucket, Key=key)

    def public_url(self, key: str) -> str:
        return f"{self._public_base_url}/{key}"

    async def ensure_public_bucket(self, public_prefix: str) -> None:
        """Local development only: creates the bucket and lets anyone read `public_prefix`.

        In production the bucket and its policy are managed by the infrastructure.
        """
        policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"AWS": ["*"]},
                    "Action": ["s3:GetObject"],
                    "Resource": [f"arn:aws:s3:::{self._bucket}/{public_prefix}*"],
                }
            ],
        }
        async with self._session.create_client("s3", **self._client_args) as client:
            existing = await client.list_buckets()
            if self._bucket not in {bucket["Name"] for bucket in existing.get("Buckets", [])}:
                await client.create_bucket(Bucket=self._bucket)
            await client.put_bucket_policy(Bucket=self._bucket, Policy=json.dumps(policy))
