"""Two-sided endpoints: customer submission + agent ticket handling."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_session
from backend.models.schemas import (
    CustomerAskRequest,
    CustomerStatusResponse,
    TicketListResponse,
    TicketRecord,
    TicketReplyRequest,
)
from backend.services.ticket_service import TicketService

router = APIRouter(prefix="/api", tags=["tickets"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]


def _svc(session: SessionDep) -> TicketService:
    return TicketService(session)


ServiceDep = Annotated[TicketService, Depends(_svc)]


# ---------------- customer side ----------------
@router.post("/customer/ask", response_model=TicketRecord)
async def customer_ask(body: CustomerAskRequest, service: ServiceDep) -> TicketRecord:
    return await service.create(
        message=body.message, customer_id=body.customer_id, product=body.product
    )


@router.get("/customer/status/{conversation_id}", response_model=CustomerStatusResponse)
async def customer_status(conversation_id: str, service: ServiceDep) -> CustomerStatusResponse:
    result = await service.customer_status(conversation_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return result


# ---------------- agent side ----------------
@router.get("/tickets", response_model=TicketListResponse)
async def list_tickets(
    service: ServiceDep,
    status: str = Query("pending"),
    limit: int = Query(100, ge=1, le=500),
) -> TicketListResponse:
    tickets, total = await service.list(status=status, limit=limit)
    return TicketListResponse(tickets=tickets, total=total)


@router.get("/tickets/{ticket_id}", response_model=TicketRecord)
async def get_ticket(ticket_id: int, service: ServiceDep) -> TicketRecord:
    ticket = await service.get(ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


@router.post("/tickets/{ticket_id}/reply", response_model=TicketRecord)
async def reply_ticket(
    ticket_id: int, body: TicketReplyRequest, service: ServiceDep
) -> TicketRecord:
    ticket = await service.reply(
        ticket_id,
        reply=body.reply,
        agent_name=body.agent_name,
        confidence=body.confidence,
        resolved=body.resolved,
    )
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket
