#!/usr/bin/env python3
"""
Test script for NLP functionality in AI Service
This script tests the entity extraction capabilities of the AI service.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.ai_service import AIService
from app.models.ai_chat_models import AIChatSession
import json

def test_nlp_parsing():
    """Test the NLP parsing functionality with sample AI responses."""
    
    ai_service = AIService()
    
    # Create a mock session
    mock_session = AIChatSession()
    mock_session.event_data = json.dumps({})
    
    # Test cases with different types of AI responses
    test_cases = [
        {
            "name": "Birthday Party",
            "text": "Let's plan a birthday party for Sarah on December 15th, 2024 at Central Park. We're expecting about 25 people and it should last for 3 hours.",
            "expected": {
                "title": "birthday party",
                "event_type": "birthday",
                "location": "Central Park",
                "guest_count": 25,
                "duration": "3 hours"
            }
        },
        {
            "name": "Business Meeting",
            "text": "I need to schedule a meeting called 'Quarterly Review' for next Monday at 2:00 PM in the conference room. About 10 attendees expected.",
            "expected": {
                "title": "Quarterly Review",
                "event_type": "meeting",
                "location": "conference room",
                "guest_count": 10
            }
        },
        {
            "name": "Wedding Reception",
            "text": "Planning a wedding reception on June 20th, 2024 at the Grand Hotel ballroom for 150 guests. The celebration will last 5 hours.",
            "expected": {
                "event_type": "wedding",
                "location": "Grand Hotel ballroom",
                "guest_count": 150,
                "duration": "5 hours"
            }
        },
        {
            "name": "Casual Dinner",
            "text": "Let's have dinner at Mario's Restaurant this Friday evening. Just a small gathering for 6 people.",
            "expected": {
                "event_type": "dinner",
                "location": "Mario's Restaurant",
                "guest_count": 6
            }
        },
        {
            "name": "Workshop",
            "text": "I'm organizing a Python workshop titled 'Advanced Data Science' on March 10th at the Tech Center. Expecting 30 participants for a 4-hour session.",
            "expected": {
                "title": "Advanced Data Science",
                "event_type": "workshop",
                "location": "Tech Center",
                "guest_count": 30,
                "duration": "4 hours"
            }
        }
    ]
    
    print(" Testing NLP Entity Extraction Functionality")
    print("=" * 60)
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n Test Case {i}: {test_case['name']}")
        print(f"Input: {test_case['text']}")
        
        # Parse the AI response
        result = ai_service._parse_ai_response(test_case['text'], mock_session)
        
        print(f"Extracted Data: {result.get('event_data', {})}")
        print(f"Suggestions: {result.get('suggestions', [])}")
        
        # Check if event preview was created
        if result.get('event_preview'):
            print(f"Event Preview: {result['event_preview']}")
        
        # Validate extraction
        extracted_data = result.get('event_data', {})
        expected = test_case['expected']
        
        print("\n Validation Results:")
        for key, expected_value in expected.items():
            actual_value = extracted_data.get(key)
            if actual_value:
                if isinstance(expected_value, str) and expected_value.lower() in str(actual_value).lower():
                    print(f"   {key}: Found '{actual_value}' (contains '{expected_value}')")
                elif actual_value == expected_value:
                    print(f"   {key}: Exact match '{actual_value}'")
                else:
                    print(f"    {key}: Expected '{expected_value}', got '{actual_value}'")
            else:
                print(f"   {key}: Not extracted (expected '{expected_value}')")
        
        print("-" * 40)
    
    print("\n Testing Individual Entity Extraction Methods")
    print("=" * 60)
    
    # Test individual methods
    test_text = "Let's have a birthday party for John on Saturday, December 25th at 123 Main Street Restaurant for 20 people lasting 2 hours"
    
    print(f"Test Text: {test_text}")
    print(f"Title: {ai_service._extract_event_title(test_text)}")
    print(f"Dates: {ai_service._extract_dates(test_text)}")
    print(f"Location: {ai_service._extract_location(test_text)}")
    print(f"Numbers: {ai_service._extract_numbers(test_text)}")
    print(f"Event Type: {ai_service._extract_event_type(test_text)}")
    print(f"Description: {ai_service._extract_description(test_text)}")
    
    print("\n NLP Testing Complete!")

if __name__ == "__main__":
    test_nlp_parsing()