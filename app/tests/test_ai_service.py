import pytest
from unittest.mock import Mock, patch, AsyncMock
from app.services.ai_service import AIService
from app.core.errors import ValidationError
import json
from datetime import datetime, timedelta

class TestAIService:
    """Test cases for AIService."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.ai_service = AIService()
        self.sample_event_data = {
            "event_type": "birthday",
            "budget": 500,
            "guest_count": 20,
            "location": "New York",
            "date": "2024-12-25",
            "preferences": ["outdoor", "casual"]
        }
    
    @pytest.mark.asyncio
    @patch('openai.ChatCompletion.acreate')
    async def test_generate_event_checklist_success(self, mock_openai):
        """Test successful event checklist generation."""
        mock_response = {
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "checklist": [
                            {"task": "Book venue", "priority": "high", "deadline": "2 weeks before"},
                            {"task": "Send invitations", "priority": "high", "deadline": "3 weeks before"},
                            {"task": "Order cake", "priority": "medium", "deadline": "1 week before"}
                        ],
                        "estimated_timeline": "4-6 weeks",
                        "budget_breakdown": {
                            "venue": 200,
                            "food": 150,
                            "decorations": 100,
                            "entertainment": 50
                        }
                    })
                }
            }]
        }
        mock_openai.return_value = mock_response
        
        result = await self.ai_service.generate_event_checklist(self.sample_event_data)
        
        assert "checklist" in result
        assert "estimated_timeline" in result
        assert "budget_breakdown" in result
        assert len(result["checklist"]) == 3
        assert result["checklist"][0]["task"] == "Book venue"
        mock_openai.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('openai.ChatCompletion.acreate')
    async def test_generate_event_checklist_openai_failure(self, mock_openai):
        """Test event checklist generation when OpenAI fails."""
        mock_openai.side_effect = Exception("OpenAI API Error")
        
        result = await self.ai_service.generate_event_checklist(self.sample_event_data)
        
        # Should return fallback checklist
        assert "checklist" in result
        assert "error" in result
        assert result["error"] == "AI service temporarily unavailable"
        assert len(result["checklist"]) > 0  # Fallback should have items
    
    @pytest.mark.asyncio
    @patch('openai.ChatCompletion.acreate')
    async def test_suggest_vendors_success(self, mock_openai):
        """Test successful vendor suggestions."""
        mock_response = {
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "vendors": {
                            "catering": [
                                {"name": "Delicious Catering", "specialty": "Italian cuisine", "price_range": "$$"},
                                {"name": "Party Foods Inc", "specialty": "Buffet style", "price_range": "$"}
                            ],
                            "photography": [
                                {"name": "Capture Moments", "specialty": "Event photography", "price_range": "$$$"}
                            ]
                        },
                        "recommendations": "Book catering early for better rates"
                    })
                }
            }]
        }
        mock_openai.return_value = mock_response
        
        vendor_categories = ["catering", "photography"]
        result = await self.ai_service.suggest_vendors(self.sample_event_data, vendor_categories)
        
        assert "vendors" in result
        assert "catering" in result["vendors"]
        assert "photography" in result["vendors"]
        assert len(result["vendors"]["catering"]) == 2
        assert "recommendations" in result
        mock_openai.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('openai.ChatCompletion.acreate')
    async def test_suggest_vendors_with_fallback(self, mock_openai):
        """Test vendor suggestions with fallback when AI fails."""
        mock_openai.side_effect = Exception("API Error")
        
        vendor_categories = ["catering", "photography"]
        result = await self.ai_service.suggest_vendors(self.sample_event_data, vendor_categories)
        
        assert "vendors" in result
        assert "error" in result
        assert "catering" in result["vendors"]
        assert "photography" in result["vendors"]
    
    @pytest.mark.asyncio
    @patch('openai.ChatCompletion.acreate')
    async def test_generate_menu_suggestions_success(self, mock_openai):
        """Test successful menu generation."""
        mock_response = {
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "menu": {
                            "appetizers": ["Bruschetta", "Cheese platter"],
                            "main_courses": ["Grilled chicken", "Vegetarian pasta"],
                            "desserts": ["Birthday cake", "Ice cream"]
                        },
                        "dietary_accommodations": {
                            "vegetarian": ["Vegetarian pasta", "Cheese platter"],
                            "gluten_free": ["Grilled chicken"]
                        },
                        "estimated_cost_per_person": 25,
                        "shopping_list": ["Chicken breast", "Pasta", "Tomatoes"]
                    })
                }
            }]
        }
        mock_openai.return_value = mock_response
        
        dietary_restrictions = ["vegetarian", "gluten_free"]
        result = await self.ai_service.generate_menu_suggestions(
            self.sample_event_data, dietary_restrictions
        )
        
        assert "menu" in result
        assert "dietary_accommodations" in result
        assert "estimated_cost_per_person" in result
        assert "shopping_list" in result
        assert "appetizers" in result["menu"]
        mock_openai.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('openai.ChatCompletion.acreate')
    async def test_optimize_budget_success(self, mock_openai):
        """Test successful budget optimization."""
        mock_response = {
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "optimized_budget": {
                            "venue": 150,
                            "food": 200,
                            "decorations": 75,
                            "entertainment": 75
                        },
                        "savings_suggestions": [
                            {"category": "venue", "suggestion": "Consider community centers", "potential_savings": 50},
                            {"category": "decorations", "suggestion": "DIY decorations", "potential_savings": 25}
                        ],
                        "total_savings": 75,
                        "priority_items": ["venue", "food"]
                    })
                }
            }]
        }
        mock_openai.return_value = mock_response
        
        current_budget = {
            "venue": 200,
            "food": 200,
            "decorations": 100,
            "entertainment": 100
        }
        
        result = await self.ai_service.optimize_budget(self.sample_event_data, current_budget)
        
        assert "optimized_budget" in result
        assert "savings_suggestions" in result
        assert "total_savings" in result
        assert result["total_savings"] == 75
        mock_openai.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('openai.ChatCompletion.acreate')
    async def test_generate_event_timeline_success(self, mock_openai):
        """Test successful event timeline generation."""
        mock_response = {
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "timeline": [
                            {"time": "6:00 PM", "activity": "Guest arrival", "duration": "30 minutes"},
                            {"time": "6:30 PM", "activity": "Welcome drinks", "duration": "30 minutes"},
                            {"time": "7:00 PM", "activity": "Dinner service", "duration": "60 minutes"},
                            {"time": "8:00 PM", "activity": "Birthday cake", "duration": "15 minutes"}
                        ],
                        "total_duration": "2 hours 15 minutes",
                        "setup_time": "2 hours before",
                        "cleanup_time": "1 hour after"
                    })
                }
            }]
        }
        mock_openai.return_value = mock_response
        
        result = await self.ai_service.generate_event_timeline(self.sample_event_data)
        
        assert "timeline" in result
        assert "total_duration" in result
        assert "setup_time" in result
        assert len(result["timeline"]) == 4
        mock_openai.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('openai.ChatCompletion.acreate')
    async def test_suggest_gift_ideas_success(self, mock_openai):
        """Test successful gift idea generation."""
        mock_response = {
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "gift_ideas": [
                            {"item": "Personalized photo album", "price_range": "$20-40", "category": "personal"},
                            {"item": "Cooking class voucher", "price_range": "$50-100", "category": "experience"},
                            {"item": "Bluetooth speaker", "price_range": "$30-80", "category": "tech"}
                        ],
                        "personalized_suggestions": "Based on their love for cooking",
                        "group_gift_ideas": ["Weekend getaway", "Professional photography session"]
                    })
                }
            }]
        }
        mock_openai.return_value = mock_response
        
        recipient_info = {
            "age": 30,
            "interests": ["cooking", "photography"],
            "relationship": "friend"
        }
        
        result = await self.ai_service.suggest_gift_ideas(self.sample_event_data, recipient_info)
        
        assert "gift_ideas" in result
        assert "personalized_suggestions" in result
        assert "group_gift_ideas" in result
        assert len(result["gift_ideas"]) == 3
        mock_openai.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('httpx.AsyncClient')
    async def test_check_weather_and_suggest_backup_success(self, mock_client):
        """Test successful weather check and backup suggestions."""
        # Mock weather API response
        mock_weather_response = Mock()
        mock_weather_response.status_code = 200
        mock_weather_response.json.return_value = {
            "current": {
                "condition": {"text": "Partly cloudy"},
                "temp_c": 22,
                "humidity": 65
            },
            "forecast": {
                "forecastday": [{
                    "day": {
                        "condition": {"text": "Light rain"},
                        "maxtemp_c": 20,
                        "mintemp_c": 15,
                        "daily_chance_of_rain": 70
                    }
                }]
            }
        }
        
        mock_client_instance = Mock()
        mock_client_instance.get = AsyncMock(return_value=mock_weather_response)
        mock_client.return_value.__aenter__.return_value = mock_client_instance
        
        # Mock OpenAI for backup suggestions
        with patch('openai.ChatCompletion.acreate') as mock_openai:
            mock_openai.return_value = {
                "choices": [{
                    "message": {
                        "content": json.dumps({
                            "backup_plan": {
                                "indoor_venue": "Community center",
                                "covered_areas": ["Pavilion", "Tent rental"],
                                "weather_contingencies": ["Umbrellas", "Heaters"]
                            },
                            "recommendations": "Consider renting a tent"
                        })
                    }
                }]
            }
            
            result = await self.ai_service.check_weather_and_suggest_backup(
                self.sample_event_data, "New York"
            )
        
        assert "current_weather" in result
        assert "forecast" in result
        assert "backup_plan" in result
        assert "recommendations" in result
        assert result["current_weather"]["condition"] == "Partly cloudy"
        mock_client_instance.get.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('httpx.AsyncClient')
    async def test_check_weather_api_failure(self, mock_client):
        """Test weather check when API fails."""
        mock_client_instance = Mock()
        mock_client_instance.get = AsyncMock(side_effect=Exception("API Error"))
        mock_client.return_value.__aenter__.return_value = mock_client_instance
        
        result = await self.ai_service.check_weather_and_suggest_backup(
            self.sample_event_data, "New York"
        )
        
        assert "error" in result
        assert "backup_plan" in result  # Should still provide generic backup
        assert result["error"] == "Weather service temporarily unavailable"
    
    def test_build_event_prompt(self):
        """Test event prompt building."""
        prompt = self.ai_service._build_event_prompt(self.sample_event_data)
        
        assert "birthday" in prompt
        assert "$500" in prompt
        assert "20 guests" in prompt
        assert "New York" in prompt
        assert "outdoor" in prompt
        assert "casual" in prompt
    
    def test_build_vendor_prompt(self):
        """Test vendor prompt building."""
        vendor_categories = ["catering", "photography"]
        prompt = self.ai_service._build_vendor_prompt(self.sample_event_data, vendor_categories)
        
        assert "catering" in prompt
        assert "photography" in prompt
        assert "birthday" in prompt
        assert "New York" in prompt
    
    def test_build_menu_prompt(self):
        """Test menu prompt building."""
        dietary_restrictions = ["vegetarian", "gluten_free"]
        prompt = self.ai_service._build_menu_prompt(self.sample_event_data, dietary_restrictions)
        
        assert "vegetarian" in prompt
        assert "gluten_free" in prompt
        assert "20 guests" in prompt
        assert "birthday" in prompt
    
    def test_build_budget_prompt(self):
        """Test budget optimization prompt building."""
        current_budget = {"venue": 200, "food": 150}
        prompt = self.ai_service._build_budget_prompt(self.sample_event_data, current_budget)
        
        assert "$500" in prompt  # Total budget
        assert "venue: $200" in prompt
        assert "food: $150" in prompt
        assert "optimize" in prompt.lower()
    
    def test_build_timeline_prompt(self):
        """Test timeline prompt building."""
        prompt = self.ai_service._build_timeline_prompt(self.sample_event_data)
        
        assert "birthday" in prompt
        assert "20 guests" in prompt
        assert "timeline" in prompt.lower()
        assert "schedule" in prompt.lower()
    
    def test_build_gift_prompt(self):
        """Test gift ideas prompt building."""
        recipient_info = {"age": 30, "interests": ["cooking"], "relationship": "friend"}
        prompt = self.ai_service._build_gift_prompt(self.sample_event_data, recipient_info)
        
        assert "30" in prompt
        assert "cooking" in prompt
        assert "friend" in prompt
        assert "birthday" in prompt
    
    def test_build_weather_backup_prompt(self):
        """Test weather backup prompt building."""
        weather_data = {
            "condition": "Light rain",
            "temperature": 20,
            "chance_of_rain": 70
        }
        prompt = self.ai_service._build_weather_backup_prompt(self.sample_event_data, weather_data)
        
        assert "Light rain" in prompt
        assert "70%" in prompt
        assert "outdoor" in prompt
        assert "backup" in prompt.lower()
    
    def test_get_fallback_checklist(self):
        """Test fallback checklist generation."""
        fallback = self.ai_service._get_fallback_checklist(self.sample_event_data)
        
        assert "checklist" in fallback
        assert "error" in fallback
        assert len(fallback["checklist"]) > 0
        assert fallback["error"] == "AI service temporarily unavailable"
    
    def test_get_fallback_vendors(self):
        """Test fallback vendor suggestions."""
        vendor_categories = ["catering", "photography"]
        fallback = self.ai_service._get_fallback_vendors(self.sample_event_data, vendor_categories)
        
        assert "vendors" in fallback
        assert "error" in fallback
        assert "catering" in fallback["vendors"]
        assert "photography" in fallback["vendors"]
    
    def test_get_fallback_menu(self):
        """Test fallback menu suggestions."""
        dietary_restrictions = ["vegetarian"]
        fallback = self.ai_service._get_fallback_menu(self.sample_event_data, dietary_restrictions)
        
        assert "menu" in fallback
        assert "error" in fallback
        assert "appetizers" in fallback["menu"]
        assert "main_courses" in fallback["menu"]
    
    def test_get_fallback_budget(self):
        """Test fallback budget optimization."""
        current_budget = {"venue": 200, "food": 150}
        fallback = self.ai_service._get_fallback_budget(self.sample_event_data, current_budget)
        
        assert "optimized_budget" in fallback
        assert "error" in fallback
        assert "savings_suggestions" in fallback
    
    def test_get_fallback_timeline(self):
        """Test fallback timeline generation."""
        fallback = self.ai_service._get_fallback_timeline(self.sample_event_data)
        
        assert "timeline" in fallback
        assert "error" in fallback
        assert len(fallback["timeline"]) > 0
    
    def test_get_fallback_gifts(self):
        """Test fallback gift suggestions."""
        recipient_info = {"age": 30, "interests": ["cooking"]}
        fallback = self.ai_service._get_fallback_gifts(self.sample_event_data, recipient_info)
        
        assert "gift_ideas" in fallback
        assert "error" in fallback
        assert len(fallback["gift_ideas"]) > 0
    
    def test_get_fallback_weather_backup(self):
        """Test fallback weather backup suggestions."""
        fallback = self.ai_service._get_fallback_weather_backup(self.sample_event_data)
        
        assert "backup_plan" in fallback
        assert "error" in fallback
        assert "indoor_venue" in fallback["backup_plan"]
    
    @pytest.mark.asyncio
    async def test_invalid_event_data(self):
        """Test handling of invalid event data."""
        invalid_data = {}  # Empty data
        
        result = await self.ai_service.generate_event_checklist(invalid_data)
        
        # Should still return fallback
        assert "checklist" in result
        assert "error" in result
    
    @pytest.mark.asyncio
    @patch('openai.ChatCompletion.acreate')
    async def test_malformed_ai_response(self, mock_openai):
        """Test handling of malformed AI responses."""
        mock_openai.return_value = {
            "choices": [{
                "message": {
                    "content": "Invalid JSON response"
                }
            }]
        }
        
        result = await self.ai_service.generate_event_checklist(self.sample_event_data)
        
        # Should return fallback when JSON parsing fails
        assert "checklist" in result
        assert "error" in result