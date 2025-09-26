from typing import Generic, TypeVar, List, Optional
from pydantic import BaseModel, Field
from math import ceil

T = TypeVar('T')

class PaginationParams(BaseModel):
    """Schema for pagination parameters"""
    page: int = Field(default=1, ge=1, description="Page number (1-based)")
    size: int = Field(default=20, ge=1, le=100, description="Number of items per page")
    
    @property
    def offset(self) -> int:
        """Calculate offset for database queries"""
        return (self.page - 1) * self.size
    
    @property
    def limit(self) -> int:
        """Get limit for database queries"""
        return self.size

class PaginationMeta(BaseModel):
    """Schema for pagination metadata"""
    page: int = Field(..., description="Current page number")
    size: int = Field(..., description="Number of items per page")
    total: int = Field(..., description="Total number of items")
    pages: int = Field(..., description="Total number of pages")
    has_next: bool = Field(..., description="Whether there is a next page")
    has_prev: bool = Field(..., description="Whether there is a previous page")
    next_page: Optional[int] = Field(None, description="Next page number if available")
    prev_page: Optional[int] = Field(None, description="Previous page number if available")
    
    @classmethod
    def create(cls, page: int, size: int, total: int) -> 'PaginationMeta':
        """Create pagination metadata from parameters"""
        pages = ceil(total / size) if total > 0 else 0
        has_next = page < pages
        has_prev = page > 1
        next_page = page + 1 if has_next else None
        prev_page = page - 1 if has_prev else None
        
        return cls(
            page=page,
            size=size,
            total=total,
            pages=pages,
            has_next=has_next,
            has_prev=has_prev,
            next_page=next_page,
            prev_page=prev_page
        )

class PaginatedResponse(BaseModel, Generic[T]):
    """Generic schema for paginated responses"""
    items: List[T] = Field(..., description="List of items")
    meta: PaginationMeta = Field(..., description="Pagination metadata")
    
    @classmethod
    def create(cls, items: List[T], page: int, size: int, total: int) -> 'PaginatedResponse[T]':
        """Create paginated response from items and pagination info"""
        meta = PaginationMeta.create(page=page, size=size, total=total)
        return cls(items=items, meta=meta)

class SortParams(BaseModel):
    """Schema for sorting parameters"""
    sort_by: Optional[str] = Field(None, description="Field to sort by")
    sort_order: str = Field(default="asc", regex=r"^(asc|desc)$", description="Sort order (asc or desc)")
    
    def get_order_by(self, default_field: str = "created_at") -> str:
        """Get order by clause for database queries"""
        field = self.sort_by or default_field
        order = "DESC" if self.sort_order == "desc" else "ASC"
        return f"{field} {order}"

class SearchParams(BaseModel):
    """Schema for search parameters"""
    q: Optional[str] = Field(None, min_length=1, max_length=100, description="Search query")
    
class FilterParams(BaseModel):
    """Base schema for filter parameters"""
    created_after: Optional[str] = Field(None, description="Filter items created after this date (ISO format)")
    created_before: Optional[str] = Field(None, description="Filter items created before this date (ISO format)")
    is_active: Optional[bool] = Field(None, description="Filter by active status")

class CombinedParams(PaginationParams, SortParams, SearchParams, FilterParams):
    """Combined schema for pagination, sorting, searching, and filtering"""
    pass

# Response schemas for common list endpoints
class ListResponse(BaseModel, Generic[T]):
    """Generic schema for simple list responses (without pagination)"""
    items: List[T] = Field(..., description="List of items")
    total: int = Field(..., description="Total number of items")
    
    @classmethod
    def create(cls, items: List[T], total: Optional[int] = None) -> 'ListResponse[T]':
        """Create list response from items"""
        if total is None:
            total = len(items)
        return cls(items=items, total=total)

class CountResponse(BaseModel):
    """Schema for count responses"""
    count: int = Field(..., description="Number of items")
    
class BulkOperationResponse(BaseModel):
    """Schema for bulk operation responses"""
    success_count: int = Field(..., description="Number of successful operations")
    error_count: int = Field(..., description="Number of failed operations")
    errors: List[str] = Field(default=[], description="List of error messages")
    
    @property
    def total_count(self) -> int:
        """Get total number of operations"""
        return self.success_count + self.error_count
    
    @property
    def success_rate(self) -> float:
        """Get success rate as percentage"""
        total = self.total_count
        if total == 0:
            return 0.0
        return (self.success_count / total) * 100