from sqlalchemy import Column, String, Text, Integer, Float, Boolean, ForeignKey, DateTime, Index
from sqlalchemy.orm import relationship
from app.db.base import Base
from app.models.shared_models import (
    TimestampMixin, SoftDeleteMixin, ActiveMixin, IDMixin, MediaType
)

class Media(Base, IDMixin, TimestampMixin, SoftDeleteMixin, ActiveMixin):
    """Media files model (images, videos, documents)"""
    __tablename__ = "media"
    
    # File information
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_url = Column(String(500), nullable=False)
    
    # File metadata
    file_size = Column(Integer, nullable=False)  # in bytes
    mime_type = Column(String(100), nullable=False)
    media_type = Column(String(20), nullable=False)  # image, video, document, audio
    
    # Image/Video specific metadata
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    duration = Column(Float, nullable=True)  # for videos/audio in seconds
    
    # Content information
    title = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    alt_text = Column(String(255), nullable=True)  # for accessibility
    
    # Upload information
    uploaded_by_id = Column(ForeignKey("users.id"), nullable=False)
    event_id = Column(ForeignKey("events.id"), nullable=True)  # Optional event association
    
    # Privacy and sharing
    is_public = Column(Boolean, default=False, nullable=False)
    is_featured = Column(Boolean, default=False, nullable=False)  # Featured in event gallery
    
    # Processing status (for videos/large files)
    is_processed = Column(Boolean, default=True, nullable=False)
    processing_status = Column(String(50), nullable=True)  # pending, processing, completed, failed
    
    # Thumbnail information (for videos/documents)
    thumbnail_url = Column(String(500), nullable=True)
    
    # Relationships
    uploaded_by = relationship("User", foreign_keys=[uploaded_by_id], back_populates="uploaded_media")
    event = relationship("Event", back_populates="media")
    tags = relationship("MediaTag", back_populates="media", cascade="all, delete-orphan")
    
    # Database indexes for performance optimization
    __table_args__ = (
        Index('idx_media_uploaded_by_id', 'uploaded_by_id'),
        Index('idx_media_event_id', 'event_id'),
        Index('idx_media_media_type', 'media_type'),
        Index('idx_media_mime_type', 'mime_type'),
        Index('idx_media_file_size', 'file_size'),
        Index('idx_media_is_public', 'is_public'),
        Index('idx_media_is_featured', 'is_featured'),
        Index('idx_media_is_processed', 'is_processed'),
        Index('idx_media_processing_status', 'processing_status'),
        Index('idx_media_is_active', 'is_active'),
        Index('idx_media_is_deleted', 'is_deleted'),
        Index('idx_media_created_at', 'created_at'),
        Index('idx_media_updated_at', 'updated_at'),
        # Combined indexes for common queries
        Index('idx_media_uploaded_by_created', 'uploaded_by_id', 'created_at'),
        Index('idx_media_event_created', 'event_id', 'created_at'),
        Index('idx_media_type_public', 'media_type', 'is_public'),
        Index('idx_media_event_type', 'event_id', 'media_type'),
        Index('idx_media_event_featured', 'event_id', 'is_featured'),
        Index('idx_media_uploaded_by_type', 'uploaded_by_id', 'media_type'),
    )
    
    def __repr__(self):
        return f"<Media(id={self.id}, filename='{self.filename}', type='{self.media_type}')>"
    
    @property
    def file_size_mb(self):
        """Get file size in MB"""
        return round(self.file_size / (1024 * 1024), 2)
    
    @property
    def is_image(self):
        """Check if media is an image"""
        return self.media_type == MediaType.IMAGE
    
    @property
    def is_video(self):
        """Check if media is a video"""
        return self.media_type == MediaType.VIDEO
    
    @property
    def is_document(self):
        """Check if media is a document"""
        return self.media_type == MediaType.DOCUMENT

class MediaTag(Base, IDMixin, TimestampMixin):
    """Tags for media files"""
    __tablename__ = "media_tags"
    
    media_id = Column(ForeignKey("media.id"), nullable=False)
    tag_name = Column(String(100), nullable=False)
    
    # Relationships
    media = relationship("Media", back_populates="tags")
    
    # Database indexes for performance optimization
    __table_args__ = (
        Index('idx_mediatag_media_id', 'media_id'),
        Index('idx_mediatag_tag_name', 'tag_name'),
        Index('idx_mediatag_created_at', 'created_at'),
        # Combined indexes for common queries
        Index('idx_mediatag_media_tag', 'media_id', 'tag_name'),
    )
    
    def __repr__(self):
        return f"<MediaTag(media_id={self.media_id}, tag='{self.tag_name}')>"

class MediaCollection(Base, IDMixin, TimestampMixin, SoftDeleteMixin):
    """Collections/albums of media files"""
    __tablename__ = "media_collections"
    
    # Collection information
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    # Collection settings
    is_public = Column(Boolean, default=False, nullable=False)
    cover_media_id = Column(ForeignKey("media.id"), nullable=True)
    
    # Owner and event association
    owner_id = Column(ForeignKey("users.id"), nullable=False)
    event_id = Column(ForeignKey("events.id"), nullable=True)
    
    # Relationships
    owner = relationship("User", backref="media_collections")
    event = relationship("Event", backref="media_collections")
    cover_media = relationship("Media", foreign_keys=[cover_media_id])
    items = relationship("MediaCollectionItem", back_populates="collection", cascade="all, delete-orphan")
    
    # Database indexes for performance optimization
    __table_args__ = (
        Index('idx_mediacollection_owner_id', 'owner_id'),
        Index('idx_mediacollection_event_id', 'event_id'),
        Index('idx_mediacollection_cover_media_id', 'cover_media_id'),
        Index('idx_mediacollection_is_public', 'is_public'),
        Index('idx_mediacollection_is_deleted', 'is_deleted'),
        Index('idx_mediacollection_created_at', 'created_at'),
        Index('idx_mediacollection_updated_at', 'updated_at'),
        # Combined indexes for common queries
        Index('idx_mediacollection_owner_created', 'owner_id', 'created_at'),
        Index('idx_mediacollection_event_created', 'event_id', 'created_at'),
        Index('idx_mediacollection_owner_public', 'owner_id', 'is_public'),
        Index('idx_mediacollection_event_public', 'event_id', 'is_public'),
    )
    
    def __repr__(self):
        return f"<MediaCollection(id={self.id}, name='{self.name}', owner_id={self.owner_id})>"
    
    @property
    def media_count(self):
        """Get count of media items in collection"""
        return len(self.items)

class MediaCollectionItem(Base, IDMixin, TimestampMixin):
    """Items in a media collection"""
    __tablename__ = "media_collection_items"
    
    collection_id = Column(ForeignKey("media_collections.id"), nullable=False)
    media_id = Column(ForeignKey("media.id"), nullable=False)
    
    # Item metadata
    order_index = Column(Integer, default=0, nullable=False)
    caption = Column(Text, nullable=True)
    
    # Relationships
    collection = relationship("MediaCollection", back_populates="items")
    media = relationship("Media", backref="collection_items")
    
    # Database indexes for performance optimization
    __table_args__ = (
        Index('idx_mediacollectionitem_collection_id', 'collection_id'),
        Index('idx_mediacollectionitem_media_id', 'media_id'),
        Index('idx_mediacollectionitem_order_index', 'order_index'),
        Index('idx_mediacollectionitem_created_at', 'created_at'),
        # Combined indexes for common queries
        Index('idx_mediacollectionitem_collection_order', 'collection_id', 'order_index'),
        Index('idx_mediacollectionitem_collection_media', 'collection_id', 'media_id'),
    )
    
    def __repr__(self):
        return f"<MediaCollectionItem(collection_id={self.collection_id}, media_id={self.media_id})>"

class MediaShare(Base, IDMixin, TimestampMixin):
    """Media sharing permissions"""
    __tablename__ = "media_shares"
    
    media_id = Column(ForeignKey("media.id"), nullable=False)
    shared_with_user_id = Column(ForeignKey("users.id"), nullable=False)
    shared_by_user_id = Column(ForeignKey("users.id"), nullable=False)
    
    # Share settings
    can_download = Column(Boolean, default=True, nullable=False)
    can_reshare = Column(Boolean, default=False, nullable=False)
    expires_at = Column(DateTime, nullable=True)
    
    # Share metadata
    share_message = Column(Text, nullable=True)
    
    # Relationships
    media = relationship("Media", backref="shares")
    shared_with = relationship("User", foreign_keys=[shared_with_user_id], back_populates="received_media_shares")
    shared_by = relationship("User", foreign_keys=[shared_by_user_id], back_populates="media_shares")
    
    # Database indexes for performance optimization
    __table_args__ = (
        Index('idx_mediashare_media_id', 'media_id'),
        Index('idx_mediashare_shared_with_user_id', 'shared_with_user_id'),
        Index('idx_mediashare_shared_by_user_id', 'shared_by_user_id'),
        Index('idx_mediashare_can_download', 'can_download'),
        Index('idx_mediashare_can_reshare', 'can_reshare'),
        Index('idx_mediashare_expires_at', 'expires_at'),
        Index('idx_mediashare_created_at', 'created_at'),
        # Combined indexes for common queries
        Index('idx_mediashare_media_shared_with', 'media_id', 'shared_with_user_id'),
        Index('idx_mediashare_shared_with_created', 'shared_with_user_id', 'created_at'),
        Index('idx_mediashare_shared_by_created', 'shared_by_user_id', 'created_at'),
    )
    
    def __repr__(self):
        return f"<MediaShare(media_id={self.media_id}, shared_with={self.shared_with_user_id})>"
    
    @property
    def is_expired(self):
        """Check if share has expired"""
        if not self.expires_at:
            return False
        from datetime import datetime
        return datetime.utcnow() > self.expires_at

class MediaLike(Base, IDMixin, TimestampMixin):
    """Media likes/reactions"""
    __tablename__ = "media_likes"
    
    media_id = Column(ForeignKey("media.id"), nullable=False)
    user_id = Column(ForeignKey("users.id"), nullable=False)
    
    # Reaction type (like, love, laugh, etc.)
    reaction_type = Column(String(20), default="like", nullable=False)
    
    # Relationships
    media = relationship("Media", backref="likes")
    user = relationship("User", foreign_keys=[user_id], back_populates="media_likes")
    
    # Database indexes for performance optimization
    __table_args__ = (
        Index('idx_medialike_media_id', 'media_id'),
        Index('idx_medialike_user_id', 'user_id'),
        Index('idx_medialike_reaction_type', 'reaction_type'),
        Index('idx_medialike_created_at', 'created_at'),
        # Combined indexes for common queries
        Index('idx_medialike_media_user', 'media_id', 'user_id'),
        Index('idx_medialike_media_reaction', 'media_id', 'reaction_type'),
        Index('idx_medialike_user_reaction', 'user_id', 'reaction_type'),
    )
    
    def __repr__(self):
        return f"<MediaLike(media_id={self.media_id}, user_id={self.user_id}, type='{self.reaction_type}')>"

class MediaComment(Base, IDMixin, TimestampMixin, SoftDeleteMixin):
    """Comments on media files"""
    __tablename__ = "media_comments"
    
    media_id = Column(ForeignKey("media.id"), nullable=False)
    author_id = Column(ForeignKey("users.id"), nullable=False)
    parent_id = Column(ForeignKey("media_comments.id"), nullable=True)  # For replies
    
    # Comment content
    content = Column(Text, nullable=False)
    
    # Relationships
    media = relationship("Media", backref="comments")
    author = relationship("User", foreign_keys=[author_id], back_populates="media_comments")
    replies = relationship("MediaComment", backref="parent", remote_side="MediaComment.id")
    
    # Database indexes for performance optimization
    __table_args__ = (
        Index('idx_mediacomment_media_id', 'media_id'),
        Index('idx_mediacomment_author_id', 'author_id'),
        Index('idx_mediacomment_parent_id', 'parent_id'),
        Index('idx_mediacomment_is_deleted', 'is_deleted'),
        Index('idx_mediacomment_created_at', 'created_at'),
        Index('idx_mediacomment_updated_at', 'updated_at'),
        # Combined indexes for common queries
        Index('idx_mediacomment_media_created', 'media_id', 'created_at'),
        Index('idx_mediacomment_author_created', 'author_id', 'created_at'),
        Index('idx_mediacomment_parent_created', 'parent_id', 'created_at'),
        Index('idx_mediacomment_media_deleted', 'media_id', 'is_deleted'),
    )
    
    def __repr__(self):
        return f"<MediaComment(id={self.id}, media_id={self.media_id}, author_id={self.author_id})>"