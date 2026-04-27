"""
Trends Service - personalized news feed for creators.
 
"""
from app.schemas.trends import TrendArticle, TrendsResponse
from app.trends.service import get_trends_for_user
 
__all__ = [
    "get_trends_for_user",
    "TrendArticle",
    "TrendsResponse",
]
 
