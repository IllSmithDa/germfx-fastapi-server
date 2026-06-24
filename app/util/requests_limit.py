from typing import Literal

from fastapi import HTTPException, Request, status


Location = Literal["query", "path"]


def validate_param_length(
    *,
    name: str,
    max_length: int,
    location: Location = "query",
    required: bool = True,
    label: str | None = None,
):
    """
    Reusable FastAPI dependency for limiting query/path parameter length.

    Example:
        q: str = Depends(validate_param_length(name="q", max_length=100))

        code: str = Depends(
            validate_param_length(name="code", max_length=25, location="path")
        )
    """

    async def dependency(request: Request) -> str | None:
        if location == "query":
            value = request.query_params.get(name)
        else:
            raw_value = request.path_params.get(name)
            value = str(raw_value) if raw_value is not None else None

        display_name = label or name

        if value is None:
            if required:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={
                        "message": f"Missing required parameter: {display_name}.",
                        "code": "MISSING_PARAMETER",
                        "parameter": name,
                    },
                )

            return None

        value = value.strip()

        if not value:
            if required:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={
                        "message": f"{display_name} cannot be empty.",
                        "code": "EMPTY_PARAMETER",
                        "parameter": name,
                    },
                )

            return None

        if len(value) > max_length:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "message": f"{display_name} must be {max_length} characters or fewer.",
                    "code": "PARAMETER_TOO_LONG",
                    "parameter": name,
                    "max_length": max_length,
                },
            )

        return value

    return dependency