from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.user_models import User
from app.models.contact_models import InvitationStatus
from app.services.contact_service import ContactService
from app.schemas.contact_schemas import (
    ContactCreate, ContactUpdate, ContactResponse, ContactListResponse,
    ContactInvitationCreate, BulkContactInvitationCreate, ContactInvitationResponse,
    InvitationListResponse, InvitationResponseRequest,
    ContactGroupCreate, ContactGroupUpdate, ContactGroupResponse, ContactGroupListResponse,
    AddContactToGroupRequest, ContactGroupMembershipResponse,
    ContactStatsResponse, ContactImportRequest, ContactImportResponse
)

router = APIRouter()


@router.post("/", response_model=ContactResponse, status_code=status.HTTP_201_CREATED)
async def create_contact(
    contact_data: ContactCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new contact"""
    contact_service = ContactService(db)
    return contact_service.add_contact(current_user.id, contact_data.model_dump())


@router.get("/", response_model=ContactListResponse)
async def get_contacts(
    search: Optional[str] = Query(None, description="Search contacts by name, phone, or email"),
    favorites_only: bool = Query(False, description="Show only favorite contacts"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(50, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user's contacts with optional filtering and pagination"""
    contact_service = ContactService(db)
    offset = (page - 1) * per_page
    
    contacts = contact_service.get_user_contacts(
        user_id=current_user.id,
        search=search,
        favorites_only=favorites_only,
        limit=per_page,
        offset=offset
    )
    
    # Get total count for pagination
    total_query = db.query(contact_service.db.query(contact_service.UserContact).filter(
        contact_service.UserContact.user_id == current_user.id
    ))
    if search:
        search_term = f"%{search}%"
        total_query = total_query.filter(
            contact_service.or_(
                contact_service.UserContact.first_name.ilike(search_term),
                contact_service.UserContact.last_name.ilike(search_term),
                contact_service.UserContact.phone_number.ilike(search_term),
                contact_service.UserContact.email.ilike(search_term)
            )
        )
    if favorites_only:
        total_query = total_query.filter(contact_service.UserContact.is_favorite == True)
    
    total = total_query.count()
    
    return ContactListResponse(
        contacts=contacts,
        total=total,
        page=page,
        per_page=per_page,
        has_next=offset + per_page < total,
        has_prev=page > 1
    )


@router.get("/{contact_id}", response_model=ContactResponse)
async def get_contact(
    contact_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific contact"""
    from app.models.contact_models import UserContact
    from sqlalchemy import and_
    
    contact = db.query(UserContact).filter(
        and_(
            UserContact.id == contact_id,
            UserContact.user_id == current_user.id
        )
    ).first()
    
    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact not found"
        )
    
    return contact


@router.put("/{contact_id}", response_model=ContactResponse)
async def update_contact(
    contact_id: int,
    contact_data: ContactUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a contact"""
    from app.models.contact_models import UserContact
    from sqlalchemy import and_
    
    contact = db.query(UserContact).filter(
        and_(
            UserContact.id == contact_id,
            UserContact.user_id == current_user.id
        )
    ).first()
    
    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact not found"
        )
    
    # Update contact fields
    update_data = contact_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(contact, field, value)
    
    db.commit()
    db.refresh(contact)
    return contact


@router.delete("/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_contact(
    contact_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a contact"""
    from app.models.contact_models import UserContact
    from sqlalchemy import and_
    
    contact = db.query(UserContact).filter(
        and_(
            UserContact.id == contact_id,
            UserContact.user_id == current_user.id
        )
    ).first()
    
    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact not found"
        )
    
    db.delete(contact)
    db.commit()


@router.post("/import", response_model=ContactImportResponse)
async def import_contacts(
    import_data: ContactImportRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Import multiple contacts"""
    contact_service = ContactService(db)
    imported_contacts = []
    errors = []
    skipped_count = 0
    
    for contact_data in import_data.contacts:
        try:
            contact = contact_service.add_contact(current_user.id, contact_data.model_dump())
            imported_contacts.append(contact)
        except HTTPException as e:
            errors.append(f"Contact {contact_data.first_name} {contact_data.last_name}: {e.detail}")
            skipped_count += 1
        except Exception as e:
            errors.append(f"Contact {contact_data.first_name} {contact_data.last_name}: {str(e)}")
            skipped_count += 1
    
    return ContactImportResponse(
        imported_count=len(imported_contacts),
        skipped_count=skipped_count,
        errors=errors,
        imported_contacts=imported_contacts
    )


# Contact Invitations
@router.post("/invitations", response_model=ContactInvitationResponse, status_code=status.HTTP_201_CREATED)
async def send_contact_invitation(
    invitation_data: ContactInvitationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Send invitation to a contact"""
    contact_service = ContactService(db)
    return contact_service.send_contact_invitation(
        sender_id=current_user.id,
        contact_id=invitation_data.contact_id,
        event_id=invitation_data.event_id,
        message=invitation_data.message
    )


@router.post("/invitations/bulk", response_model=List[ContactInvitationResponse], status_code=status.HTTP_201_CREATED)
async def send_bulk_invitations(
    invitation_data: BulkContactInvitationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Send invitations to multiple contacts"""
    contact_service = ContactService(db)
    return contact_service.bulk_send_invitations(
        sender_id=current_user.id,
        contact_ids=invitation_data.contact_ids,
        event_id=invitation_data.event_id,
        message=invitation_data.message
    )


@router.get("/invitations/sent", response_model=InvitationListResponse)
async def get_sent_invitations(
    status_filter: Optional[InvitationStatus] = Query(None, description="Filter by invitation status"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(50, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get invitations sent by user"""
    contact_service = ContactService(db)
    offset = (page - 1) * per_page
    
    invitations = contact_service.get_sent_invitations(
        user_id=current_user.id,
        status=status_filter,
        limit=per_page,
        offset=offset
    )
    
    # Get total count
    from app.models.contact_models import ContactInvitation
    total_query = db.query(ContactInvitation).filter(ContactInvitation.sender_id == current_user.id)
    if status_filter:
        total_query = total_query.filter(ContactInvitation.status == status_filter)
    total = total_query.count()
    
    return InvitationListResponse(
        invitations=invitations,
        total=total,
        page=page,
        per_page=per_page,
        has_next=offset + per_page < total,
        has_prev=page > 1
    )


@router.get("/invitations/received", response_model=InvitationListResponse)
async def get_received_invitations(
    status_filter: Optional[InvitationStatus] = Query(None, description="Filter by invitation status"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(50, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get invitations received by user"""
    contact_service = ContactService(db)
    offset = (page - 1) * per_page
    
    invitations = contact_service.get_received_invitations(
        user_id=current_user.id,
        status=status_filter,
        limit=per_page,
        offset=offset
    )
    
    # Get total count
    from app.models.contact_models import ContactInvitation
    total_query = db.query(ContactInvitation).filter(ContactInvitation.recipient_id == current_user.id)
    if status_filter:
        total_query = total_query.filter(ContactInvitation.status == status_filter)
    total = total_query.count()
    
    return InvitationListResponse(
        invitations=invitations,
        total=total,
        page=page,
        per_page=per_page,
        has_next=offset + per_page < total,
        has_prev=page > 1
    )


@router.post("/invitations/{invitation_id}/respond", response_model=ContactInvitationResponse)
async def respond_to_invitation(
    invitation_id: int,
    response_data: InvitationResponseRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Accept or decline an invitation"""
    contact_service = ContactService(db)
    return contact_service.respond_to_invitation(
        invitation_id=invitation_id,
        user_id=current_user.id,
        accept=response_data.accept
    )


# Contact Groups
@router.post("/groups", response_model=ContactGroupResponse, status_code=status.HTTP_201_CREATED)
async def create_contact_group(
    group_data: ContactGroupCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new contact group"""
    contact_service = ContactService(db)
    return contact_service.create_contact_group(
        user_id=current_user.id,
        name=group_data.name,
        description=group_data.description
    )


@router.get("/groups", response_model=ContactGroupListResponse)
async def get_contact_groups(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(50, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user's contact groups"""
    from app.models.contact_models import ContactGroup
    
    offset = (page - 1) * per_page
    
    groups = db.query(ContactGroup).filter(
        ContactGroup.user_id == current_user.id
    ).offset(offset).limit(per_page).all()
    
    total = db.query(ContactGroup).filter(ContactGroup.user_id == current_user.id).count()
    
    return ContactGroupListResponse(
        groups=groups,
        total=total,
        page=page,
        per_page=per_page,
        has_next=offset + per_page < total,
        has_prev=page > 1
    )


@router.post("/groups/{group_id}/members", response_model=ContactGroupMembershipResponse, status_code=status.HTTP_201_CREATED)
async def add_contact_to_group(
    group_id: int,
    member_data: AddContactToGroupRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Add contact to a group"""
    contact_service = ContactService(db)
    return contact_service.add_contact_to_group(
        user_id=current_user.id,
        group_id=group_id,
        contact_id=member_data.contact_id
    )


@router.get("/stats", response_model=ContactStatsResponse)
async def get_contact_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get contact statistics for the user"""
    from app.models.contact_models import UserContact, ContactGroup, ContactInvitation
    
    total_contacts = db.query(UserContact).filter(UserContact.user_id == current_user.id).count()
    favorite_contacts = db.query(UserContact).filter(
        UserContact.user_id == current_user.id,
        UserContact.is_favorite == True
    ).count()
    total_groups = db.query(ContactGroup).filter(ContactGroup.user_id == current_user.id).count()
    
    pending_sent = db.query(ContactInvitation).filter(
        ContactInvitation.sender_id == current_user.id,
        ContactInvitation.status == InvitationStatus.PENDING
    ).count()
    
    pending_received = db.query(ContactInvitation).filter(
        ContactInvitation.recipient_id == current_user.id,
        ContactInvitation.status == InvitationStatus.PENDING
    ).count()
    
    accepted = db.query(ContactInvitation).filter(
        ContactInvitation.sender_id == current_user.id,
        ContactInvitation.status == InvitationStatus.ACCEPTED
    ).count()
    
    declined = db.query(ContactInvitation).filter(
        ContactInvitation.sender_id == current_user.id,
        ContactInvitation.status == InvitationStatus.DECLINED
    ).count()
    
    return ContactStatsResponse(
        total_contacts=total_contacts,
        favorite_contacts=favorite_contacts,
        total_groups=total_groups,
        pending_invitations_sent=pending_sent,
        pending_invitations_received=pending_received,
        accepted_invitations=accepted,
        declined_invitations=declined
    )