"""
Pre-defined game templates for icebreaker, party, and team building games.
No external API required - all content is built-in or user-customizable.
"""

# ============================================================================
# ICEBREAKER GAME TEMPLATES
# ============================================================================

ICEBREAKER_TEMPLATES = {
    "two_truths_lie": {
        "title": "Two Truths and a Lie",
        "description": "Each player shares 3 statements - 2 true, 1 false. Others guess the lie!",
        "instructions": "Take turns sharing three statements about yourself. Two must be true, one must be false. Other players vote on which one they think is the lie. Reveal the answer and award points!",
        "min_players": 3,
        "max_players": 20,
        "estimated_duration_minutes": 20,
        "materials_needed": [],
        "game_data": {
            "template": "two_truths_lie",
            "rounds": 1,
            "time_per_turn_seconds": 60,
            "scoring": {
                "correct_guess": 10,
                "fool_others": 5
            },
            "rules": [
                "Each player gets one turn per round",
                "Write down your 3 statements before your turn",
                "Don't make it too obvious!",
                "Vote before the reveal"
            ]
        }
    },
    
    "never_have_i_ever": {
        "title": "Never Have I Ever",
        "description": "Players take turns saying things they've never done. Those who HAVE done it share!",
        "instructions": "Go around the circle. Each person says something they've never done starting with 'Never have I ever...'. Anyone who HAS done it must share their story!",
        "min_players": 4,
        "max_players": 20,
        "estimated_duration_minutes": 15,
        "materials_needed": [],
        "game_data": {
            "template": "never_have_i_ever",
            "prompts": [
                "Never have I ever traveled outside my country",
                "Never have I ever met a celebrity",
                "Never have I ever gone skydiving",
                "Never have I ever broken a bone",
                "Never have I ever sung karaoke",
                "Never have I ever been on TV",
                "Never have I ever ridden a horse",
                "Never have I ever been to a concert",
                "Never have I ever won a competition",
                "Never have I ever eaten sushi"
            ],
            "rounds": 2,
            "custom_prompts_allowed": True,
            "family_friendly": True
        }
    },
    
    "quick_questions": {
        "title": "Quick Questions",
        "description": "Rapid-fire questions to learn about each other!",
        "instructions": "Answer quick questions about yourself. Everyone takes turns answering the same question. Keep it fast and fun!",
        "min_players": 3,
        "max_players": 30,
        "estimated_duration_minutes": 15,
        "materials_needed": [],
        "game_data": {
            "template": "quick_questions",
            "questions": [
                "What's your favorite vacation spot?",
                "Coffee or tea?",
                "Mountains or beach?",
                "What's your hidden talent?",
                "Best concert you've attended?",
                "Favorite childhood memory?",
                "If you could have dinner with anyone, who?",
                "What's on your bucket list?",
                "Favorite movie of all time?",
                "Early bird or night owl?",
                "Cats or dogs?",
                "Favorite season?",
                "Dream job?",
                "Favorite food?",
                "Last book you read?"
            ],
            "time_per_question_seconds": 30,
            "rounds": 1
        }
    },
    
    "would_you_rather": {
        "title": "Would You Rather",
        "description": "Choose between two options and explain why!",
        "instructions": "Present two options. Everyone chooses and explains their choice. Great for sparking conversations!",
        "min_players": 2,
        "max_players": 25,
        "estimated_duration_minutes": 20,
        "materials_needed": [],
        "game_data": {
            "template": "would_you_rather",
            "questions": [
                {
                    "id": 1,
                    "text": "Would you rather...",
                    "option_a": "Travel to the past",
                    "option_b": "Travel to the future"
                },
                {
                    "id": 2,
                    "text": "Would you rather...",
                    "option_a": "Be able to fly",
                    "option_b": "Be invisible"
                },
                {
                    "id": 3,
                    "text": "Would you rather...",
                    "option_a": "Live in the city",
                    "option_b": "Live in the countryside"
                },
                {
                    "id": 4,
                    "text": "Would you rather...",
                    "option_a": "Always be 10 minutes late",
                    "option_b": "Always be 20 minutes early"
                },
                {
                    "id": 5,
                    "text": "Would you rather...",
                    "option_a": "Have unlimited money",
                    "option_b": "Have unlimited time"
                },
                {
                    "id": 6,
                    "text": "Would you rather...",
                    "option_a": "Read minds",
                    "option_b": "See the future"
                },
                {
                    "id": 7,
                    "text": "Would you rather...",
                    "option_a": "Never use social media again",
                    "option_b": "Never watch TV/movies again"
                },
                {
                    "id": 8,
                    "text": "Would you rather...",
                    "option_a": "Have a rewind button",
                    "option_b": "Have a pause button for your life"
                }
            ],
            "rounds": 1,
            "discussion_encouraged": True
        }
    },
    
    "find_someone_who": {
        "title": "Find Someone Who...",
        "description": "Mingle and find people who match different descriptions!",
        "instructions": "Walk around and talk to people. Find someone who matches each description on your card. Get their signature!",
        "min_players": 10,
        "max_players": 100,
        "estimated_duration_minutes": 15,
        "materials_needed": ["Printed cards", "Pens"],
        "game_data": {
            "template": "find_someone_who",
            "prompts": [
                "Has been to more than 5 countries",
                "Speaks more than 2 languages",
                "Has a pet",
                "Plays a musical instrument",
                "Has run a marathon",
                "Can cook 3+ cuisines",
                "Has met someone famous",
                "Has the same birth month as you",
                "Works in tech",
                "Loves spicy food",
                "Has lived in 3+ cities",
                "Enjoys hiking",
                "Has broken a bone",
                "Can juggle",
                "Has written a book or blog"
            ],
            "scoring": {
                "points_per_match": 5,
                "first_to_complete_bonus": 25
            },
            "time_limit_minutes": 15
        }
    }
}

# ============================================================================
# PARTY GAME TEMPLATES
# ============================================================================

PARTY_GAME_TEMPLATES = {
    "charades": {
        "title": "Charades",
        "description": "Act out words/phrases without speaking!",
        "instructions": "One person acts out a word or phrase while their team guesses. No talking, no sounds, just acting! Set a timer and earn points for correct guesses.",
        "min_players": 4,
        "max_players": 20,
        "estimated_duration_minutes": 30,
        "materials_needed": ["Timer"],
        "game_data": {
            "template": "charades",
            "categories": ["Movies", "Songs", "Actions", "Famous People", "Animals", "Occupations"],
            "items": [
                # Movies
                {"text": "The Lion King", "category": "Movies", "difficulty": "easy", "points": 10},
                {"text": "Inception", "category": "Movies", "difficulty": "hard", "points": 20},
                {"text": "Frozen", "category": "Movies", "difficulty": "easy", "points": 10},
                
                # Actions
                {"text": "Brushing teeth", "category": "Actions", "difficulty": "easy", "points": 10},
                {"text": "Rock climbing", "category": "Actions", "difficulty": "medium", "points": 15},
                {"text": "Juggling", "category": "Actions", "difficulty": "medium", "points": 15},
                
                # Famous People
                {"text": "Beyoncé", "category": "Famous People", "difficulty": "medium", "points": 15},
                {"text": "Michael Jackson", "category": "Famous People", "difficulty": "easy", "points": 10},
                
                # Animals
                {"text": "Kangaroo", "category": "Animals", "difficulty": "easy", "points": 10},
                {"text": "Penguin", "category": "Animals", "difficulty": "easy", "points": 10},
                {"text": "Octopus", "category": "Animals", "difficulty": "medium", "points": 15}
            ],
            "time_per_turn_seconds": 60,
            "teams_allowed": True,
            "rules": [
                "No talking or making sounds",
                "No pointing at objects in the room",
                "Can use gestures and body language",
                "Team has 60 seconds to guess"
            ]
        }
    },
    
    "pictionary": {
        "title": "Pictionary",
        "description": "Draw the word without letters or numbers!",
        "instructions": "One person draws while their team guesses the word. No letters, numbers, or symbols allowed! Just drawings!",
        "min_players": 4,
        "max_players": 20,
        "estimated_duration_minutes": 30,
        "materials_needed": ["Paper", "Markers", "Timer"],
        "game_data": {
            "template": "pictionary",
            "categories": ["Objects", "Animals", "Places", "Actions", "Food"],
            "items": [
                {"text": "Eiffel Tower", "category": "Places", "difficulty": "medium", "points": 15},
                {"text": "Elephant", "category": "Animals", "difficulty": "easy", "points": 10},
                {"text": "Cooking", "category": "Actions", "difficulty": "medium", "points": 15},
                {"text": "Pizza", "category": "Food", "difficulty": "easy", "points": 10},
                {"text": "Bicycle", "category": "Objects", "difficulty": "easy", "points": 10},
                {"text": "Swimming", "category": "Actions", "difficulty": "easy", "points": 10},
                {"text": "Statue of Liberty", "category": "Places", "difficulty": "medium", "points": 15},
                {"text": "Rainbow", "category": "Objects", "difficulty": "medium", "points": 15},
                {"text": "Birthday cake", "category": "Food", "difficulty": "easy", "points": 10},
                {"text": "Giraffe", "category": "Animals", "difficulty": "easy", "points": 10}
            ],
            "time_per_turn_seconds": 90,
            "teams_allowed": True,
            "rules": [
                "No letters or numbers",
                "No talking while drawing",
                "Can draw lines and shapes only",
                "Team has 90 seconds to guess"
            ]
        }
    },
    
    "scavenger_hunt": {
        "title": "Scavenger Hunt",
        "description": "Find items and take photos as proof!",
        "instructions": "Complete the scavenger hunt by finding all items on the list. Take photos as proof! First team to complete wins!",
        "min_players": 2,
        "max_players": 50,
        "estimated_duration_minutes": 45,
        "materials_needed": ["Smartphones for photos"],
        "game_data": {
            "template": "scavenger_hunt",
            "hunt_type": "photo",
            "items": [
                {
                    "id": 1,
                    "description": "Something blue",
                    "points": 10,
                    "hint": "Look for items in nature or clothing"
                },
                {
                    "id": 2,
                    "description": "A group selfie with 5+ people",
                    "points": 25,
                    "hint": "Get creative with poses!"
                },
                {
                    "id": 3,
                    "description": "Something that starts with your last name",
                    "points": 15,
                    "hint": "Can be any object"
                },
                {
                    "id": 4,
                    "description": "A funny sign or text",
                    "points": 20,
                    "hint": "Look for ironic or humorous signs"
                },
                {
                    "id": 5,
                    "description": "Someone's pet",
                    "points": 15,
                    "hint": "Ask permission first!"
                },
                {
                    "id": 6,
                    "description": "A creative team photo with a landmark",
                    "points": 30,
                    "hint": "Think outside the box"
                },
                {
                    "id": 7,
                    "description": "Something round",
                    "points": 10,
                    "hint": "Perfect circles count!"
                },
                {
                    "id": 8,
                    "description": "A book title with 'love' in it",
                    "points": 20,
                    "hint": "Check bookstores or libraries"
                }
            ],
            "time_limit_minutes": 45,
            "photo_required": True,
            "teams_allowed": True,
            "bonus_points": {
                "first_to_finish": 50,
                "most_creative_photos": 30
            }
        }
    },
    
    "minute_to_win_it": {
        "title": "Minute to Win It",
        "description": "Complete physical challenges in 60 seconds!",
        "instructions": "Complete the challenge within 60 seconds to earn points. Simple materials, hilarious results!",
        "min_players": 2,
        "max_players": 20,
        "estimated_duration_minutes": 30,
        "materials_needed": ["Various household items"],
        "game_data": {
            "template": "minute_to_win_it",
            "challenges": [
                {
                    "id": 1,
                    "name": "Cookie Face",
                    "description": "Move a cookie from forehead to mouth without using hands",
                    "difficulty": "medium",
                    "materials": ["Cookies"],
                    "points": 20
                },
                {
                    "id": 2,
                    "name": "Stack Attack",
                    "description": "Stack 36 cups into a pyramid and back to a single stack",
                    "difficulty": "hard",
                    "materials": ["36 plastic cups"],
                    "points": 30
                },
                {
                    "id": 3,
                    "name": "Junk in the Trunk",
                    "description": "Shake ping pong balls out of a tissue box tied to your waist",
                    "difficulty": "medium",
                    "materials": ["Tissue box", "8 ping pong balls", "Belt"],
                    "points": 20
                },
                {
                    "id": 4,
                    "name": "Face the Cookie",
                    "description": "Move cookies from forehead to mouth using only facial muscles",
                    "difficulty": "easy",
                    "materials": ["3-5 cookies"],
                    "points": 15
                },
                {
                    "id": 5,
                    "name": "Suck It Up",
                    "description": "Transfer M&Ms from one plate to another using only a straw",
                    "difficulty": "medium",
                    "materials": ["Straw", "25 M&Ms", "2 plates"],
                    "points": 20
                }
            ],
            "time_limit_seconds": 60,
            "attempts_per_challenge": 1
        }
    },
    
    "trivia_relay": {
        "title": "Trivia Relay",
        "description": "Run to answer trivia questions!",
        "instructions": "Teams line up. One person runs to answer a trivia question, then runs back to tag the next teammate. First team to answer all questions correctly wins!",
        "min_players": 6,
        "max_players": 30,
        "estimated_duration_minutes": 20,
        "materials_needed": ["Question cards", "Space to run"],
        "game_data": {
            "template": "trivia_relay",
            "note": "Use OpenTDB API to generate questions, but format as relay race",
            "teams_required": True,
            "physical_component": True,
            "scoring": {
                "correct_answer": 10,
                "speed_bonus": 5,
                "first_team_bonus": 25
            }
        }
    }
}

# ============================================================================
# TEAM BUILDING GAME TEMPLATES
# ============================================================================

TEAM_BUILDING_TEMPLATES = {
    "escape_room": {
        "title": "Escape Room Challenge",
        "description": "Solve puzzles together to escape!",
        "instructions": "Work as a team to solve puzzles and escape within the time limit. Communication is key!",
        "min_players": 4,
        "max_players": 10,
        "estimated_duration_minutes": 45,
        "materials_needed": ["Puzzle materials", "Timer", "Clue cards"],
        "game_data": {
            "template": "escape_room",
            "theme": "Mystery Mansion",
            "puzzles": [
                {
                    "id": 1,
                    "title": "Code Breaker",
                    "description": "Find the 4-digit code hidden in the room",
                    "clues": [
                        "Look for birthdays on certificates",
                        "Add all the numbers together",
                        "The code opens the locked box"
                    ],
                    "solution": "1985",
                    "points": 50,
                    "difficulty": "medium"
                },
                {
                    "id": 2,
                    "title": "Word Puzzle",
                    "description": "Unscramble the letters to find the key location",
                    "clues": [
                        "Letters: RTNEU DEURN HET RTECPE",
                        "Think about furniture",
                        "Look down"
                    ],
                    "solution": "UNDER THE CARPET",
                    "points": 40,
                    "difficulty": "easy"
                }
            ],
            "time_limit_minutes": 45,
            "hints_available": 3,
            "hint_penalty": -5
        }
    },
    
    "build_competition": {
        "title": "Build Competition",
        "description": "Build the tallest/strongest structure together!",
        "instructions": "Teams compete to build the best structure using provided materials. Judged on multiple criteria!",
        "min_players": 6,
        "max_players": 40,
        "estimated_duration_minutes": 30,
        "materials_needed": ["Building materials", "Timer", "Measuring tape"],
        "game_data": {
            "template": "build_competition",
            "challenges": [
                {
                    "name": "Tower Challenge",
                    "description": "Build the tallest freestanding tower",
                    "materials": ["50 sheets of paper", "1 roll of tape"],
                    "time_limit_minutes": 20,
                    "judging_criteria": ["Height", "Stability", "Creativity"],
                    "points_per_criteria": 25
                },
                {
                    "name": "Bridge Challenge",
                    "description": "Build a bridge that can hold the most weight",
                    "materials": ["100 popsicle sticks", "Glue", "String"],
                    "time_limit_minutes": 30,
                    "judging_criteria": ["Weight capacity", "Span length", "Design"],
                    "points_per_criteria": 30
                }
            ],
            "teams_required": True,
            "team_size": "3-5"
        }
    },
    
    "communication_challenge": {
        "title": "Communication Challenge",
        "description": "Complete tasks that require clear communication!",
        "instructions": "One person describes, others execute. Test your communication skills!",
        "min_players": 4,
        "max_players": 20,
        "estimated_duration_minutes": 25,
        "materials_needed": ["Blindfolds", "Various objects"],
        "game_data": {
            "template": "communication_challenge",
            "activities": [
                {
                    "name": "Blindfold Drawing",
                    "description": "One person describes, another draws while blindfolded",
                    "difficulty": "medium",
                    "points": 25
                },
                {
                    "name": "Back-to-Back Drawing",
                    "description": "Partners sit back-to-back. One describes an image, other draws it",
                    "difficulty": "easy",
                    "points": 20
                },
                {
                    "name": "Minefield",
                    "description": "Guide blindfolded teammate through obstacle course using only words",
                    "difficulty": "hard",
                    "points": 30
                }
            ]
        }
    },
    
    "problem_solving": {
        "title": "Problem Solving Challenge",
        "description": "Solve complex problems as a team!",
        "instructions": "Work together to solve problems. Every team member's input is valuable!",
        "min_players": 5,
        "max_players": 30,
        "estimated_duration_minutes": 40,
        "materials_needed": ["Problem cards", "Whiteboard", "Markers"],
        "game_data": {
            "template": "problem_solving",
            "scenarios": [
                {
                    "id": 1,
                    "title": "Survival Scenario",
                    "description": "Your plane crashed. Rank 15 items by importance for survival",
                    "time_limit_minutes": 15,
                    "requires_consensus": True,
                    "points": 50
                },
                {
                    "id": 2,
                    "title": "Budget Challenge",
                    "description": "Plan an event with a limited budget. Make tough choices!",
                    "time_limit_minutes": 20,
                    "requires_presentation": True,
                    "points": 50
                }
            ],
            "discussion_based": True
        }
    }
}

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_template(game_type: str, template_name: str):
    """Get a specific game template."""
    templates = {
        "icebreaker": ICEBREAKER_TEMPLATES,
        "party_game": PARTY_GAME_TEMPLATES,
        "team_building": TEAM_BUILDING_TEMPLATES
    }
    
    game_templates = templates.get(game_type, {})
    return game_templates.get(template_name)

def list_templates(game_type: str):
    """List all available templates for a game type."""
    templates = {
        "icebreaker": ICEBREAKER_TEMPLATES,
        "party_game": PARTY_GAME_TEMPLATES,
        "team_building": TEAM_BUILDING_TEMPLATES
    }
    
    game_templates = templates.get(game_type, {})
    return list(game_templates.keys())

def get_all_templates():
    """Get all game templates across all types."""
    return {
        "icebreaker": ICEBREAKER_TEMPLATES,
        "party_game": PARTY_GAME_TEMPLATES,
        "team_building": TEAM_BUILDING_TEMPLATES
    }
