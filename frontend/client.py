"""How the frontend reaches the backend.

Two implementations behind one interface:

``HttpClient``   calls the FastAPI server over HTTP. This is the architecture in
                 spec section 19 and what runs locally.
``DirectClient`` calls the very same FastAPI handler functions in-process, with
                 no server and no network.

The second exists because Streamlit Community Cloud runs a single process, so a
separate uvicorn server is not an option there. Rather than duplicate the
backend logic in the UI, ``DirectClient`` imports the route functions and calls
them directly — they are ordinary synchronous Python functions, and FastAPI's
decorators do not change that. There is therefore exactly one implementation of
the dashboard and chat logic, whichever way it is reached, and the two
deployment modes cannot drift apart.

Selection is by environment: set ``API_URL`` to use HTTP, leave it unset for
direct mode.
"""

from __future__ import annotations

import os
from typing import Protocol


class ClientError(RuntimeError):
    """A backend call failed. ``status`` mirrors the HTTP status code.

    Carrying the status even in direct mode keeps the UI's error handling
    identical in both modes — 429 still means "out of quota" whether it
    travelled over a socket or not.
    """

    def __init__(self, status: int, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.detail = detail


class Client(Protocol):
    mode: str

    def users(self) -> list[dict]: ...
    def dashboard(self, user_id: str, month: str | None = None) -> dict: ...
    def chat(self, user_id: str, message: str, thread_id: str = "default") -> dict: ...
    def reset(self, user_id: str, thread_id: str = "default") -> None: ...


class HttpClient:
    """Talks to a running FastAPI server."""

    mode = "http"

    def __init__(self, base_url: str, timeout: int = 180) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _request(self, method: str, path: str, **kwargs) -> dict:
        import requests

        try:
            response = requests.request(
                method, f"{self.base_url}{path}", timeout=self.timeout, **kwargs
            )
        except requests.RequestException as exc:
            raise ClientError(503, f"Cannot reach the backend at {self.base_url}: {exc}")

        if response.status_code >= 400:
            try:
                detail = response.json().get("detail", response.text)
            except ValueError:
                detail = response.text
            raise ClientError(response.status_code, str(detail))
        return response.json()

    def users(self) -> list[dict]:
        return self._request("GET", "/users")

    def dashboard(self, user_id: str, month: str | None = None) -> dict:
        return self._request(
            "GET", f"/dashboard/{user_id}", params={"month": month} if month else None
        )

    def chat(self, user_id: str, message: str, thread_id: str = "default") -> dict:
        return self._request(
            "POST", "/chat",
            json={"user_id": user_id, "message": message, "thread_id": thread_id},
        )

    def reset(self, user_id: str, thread_id: str = "default") -> None:
        self._request("POST", "/chat/reset", params={"user_id": user_id, "thread_id": thread_id})


class DirectClient:
    """Runs the API's own handlers in-process. No server, no network."""

    mode = "direct"

    def __init__(self) -> None:
        # Imported lazily so that merely importing this module does not pull in
        # the whole agent stack when only HttpClient is wanted.
        from fastapi import HTTPException

        from app.api import main as api

        self._api = api
        self._http_exception = HTTPException

    def _call(self, function, *args, **kwargs):
        try:
            return function(*args, **kwargs)
        except self._http_exception as exc:
            raise ClientError(exc.status_code, str(exc.detail)) from exc

    def users(self) -> list[dict]:
        return self._call(self._api.users)

    def dashboard(self, user_id: str, month: str | None = None) -> dict:
        return self._call(self._api.dashboard, user_id, month).model_dump()

    def chat(self, user_id: str, message: str, thread_id: str = "default") -> dict:
        request = self._api.ChatRequest(
            user_id=user_id, message=message, thread_id=thread_id
        )
        return self._call(self._api.chat, request).model_dump()

    def reset(self, user_id: str, thread_id: str = "default") -> None:
        self._call(self._api.reset, user_id, thread_id)


def get_client() -> Client:
    """Pick a client from the environment.

    ``API_URL`` set  -> HTTP, against that server.
    ``API_URL`` unset -> direct, everything in this process.
    """
    api_url = os.getenv("API_URL", "").strip()
    return HttpClient(api_url) if api_url else DirectClient()
