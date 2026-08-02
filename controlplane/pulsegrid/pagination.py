from rest_framework.pagination import PageNumberPagination


class DefaultPagination(PageNumberPagination):
    """Page-number pagination that honours `?page_size=`.

    DRF silently ignores the parameter unless `page_size_query_param` is set,
    which forces consumers to walk pages of data they asked for in one request.
    The cap keeps a single request from aggregating an unbounded result set.
    """

    page_size_query_param = "page_size"
    max_page_size = 1000
