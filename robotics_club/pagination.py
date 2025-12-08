"""
Pagination utilities for ELESS APIs
Implements cursor-based pagination for better performance with large datasets
"""

from django.http import JsonResponse
from urllib.parse import urlencode


def paginate_queryset(request, queryset, page_size_param='page_size', default_page_size=10, max_page_size=100):
    """
    Paginate a Django queryset based on page and page_size parameters.
    
    Args:
        request: Django request object
        queryset: Django queryset to paginate
        page_size_param: Query parameter name for page size (default: 'page_size')
        default_page_size: Default number of items per page (default: 10)
        max_page_size: Maximum allowed items per page (default: 100)
    
    Returns:
        dict with:
            - results: List of items for current page
            - next: URL for next page or None
            - previous: URL for previous page or None
            - count: Total number of items
            - page: Current page number
            - total_pages: Total number of pages
    """
    # Get pagination parameters
    try:
        page = int(request.GET.get('page', 1))
        if page < 1:
            page = 1
    except (ValueError, TypeError):
        page = 1
    
    try:
        page_size = int(request.GET.get(page_size_param, default_page_size))
        if page_size < 1:
            page_size = default_page_size
        elif page_size > max_page_size:
            page_size = max_page_size
    except (ValueError, TypeError):
        page_size = default_page_size
    
    # Get total count
    total_count = queryset.count()
    
    # Calculate pagination
    total_pages = (total_count + page_size - 1) // page_size  # Ceiling division
    
    # Get items for current page
    start_index = (page - 1) * page_size
    end_index = start_index + page_size
    page_items = queryset[start_index:end_index]
    
    # Build full URL for pagination links
    def build_pagination_url(page_num):
        if page_num < 1 or page_num > total_pages:
            return None
        
        params = request.GET.copy()
        params['page'] = page_num
        
        # Build full URL
        scheme = request.scheme
        host = request.get_host()
        path = request.path
        query_string = urlencode(params)
        
        return f"{scheme}://{host}{path}?{query_string}"
    
    # Generate next and previous URLs
    next_url = build_pagination_url(page + 1) if page < total_pages else None
    previous_url = build_pagination_url(page - 1) if page > 1 else None
    
    return {
        'results': list(page_items),
        'next': next_url,
        'previous': previous_url,
        'count': total_count,
        'page': page,
        'total_pages': total_pages,
        'page_size': page_size
    }


def create_paginated_response(request, queryset, serializer_func, page_size=10, max_page_size=100):
    """
    Helper function to create a paginated JSON response.
    
    Args:
        request: Django request object
        queryset: Django queryset to paginate
        serializer_func: Function to serialize each item (item -> dict)
        page_size: Default page size
        max_page_size: Maximum allowed page size
    
    Returns:
        JsonResponse with paginated data
    """
    paginated_data = paginate_queryset(
        request, 
        queryset, 
        default_page_size=page_size,
        max_page_size=max_page_size
    )
    
    # Serialize results
    serialized_results = []
    for item in paginated_data['results']:
        serialized_item = serializer_func(item)
        if serialized_item:
            serialized_results.append(serialized_item)
    
    # Return response with pagination metadata
    return JsonResponse({
        'results': serialized_results,
        'next': paginated_data['next'],
        'previous': paginated_data['previous'],
        'count': paginated_data['count'],
        'page': paginated_data['page'],
        'total_pages': paginated_data['total_pages']
    })
