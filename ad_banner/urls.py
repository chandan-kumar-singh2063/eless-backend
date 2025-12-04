from django.urls import path
from . import api_views

app_name = 'ad_banner'

urlpatterns = [
    # Banner API endpoint - matches Flutter expectation: GET /api/banners?populate=image
    path('api/banners/', api_views.BannerAPIView.as_view(), name='banners_api'),
]
