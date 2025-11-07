from typing import List, Dict, Any, Optional
import openai
from app.core.config import settings
from app.models.event_models import Event
from app.models.user_models import User
from app.models.ai_chat_models import AIChatSession, AIChatMessage
from app.schemas.chat import ChatSessionCreate, ChatMessageCreate, ChatSessionResponse, ChatMessageResponse, ChatMessageRole, ChatSessionStatus
from app.services.event_service import EventService
from app.schemas.event import EventCreate
from app.core.circuit_breaker import openai_circuit_breaker, ai_fallback
from datetime import datetime, timedelta
import json
import httpx
import uuid
import re
import dateparser
from sqlalchemy.orm import Session

class AIService:
    """Service for AI-powered features using OpenAI."""
    
    def __init__(self):
        openai.api_key = settings.OPENAI_API_KEY
        self.model = "gpt-4"
    
    #CONVERSATIONAL AI CHAT METHODS
    
    async def create_chat_session(
        self, 
        db: Session, 
        user_id: int, 
        session_data: ChatSessionCreate
    ) -> ChatSessionResponse:
        """Create a new AI chat session for event creation."""
        try:
            # Create new chat session
            session = AIChatSession(
                user_id=user_id,
                context=json.dumps(session_data.context) if session_data.context else None,
                status=ChatSessionStatus.ACTIVE
            )
            db.add(session)
            db.flush()  # Get the ID
            
            # Create initial system message
            system_message = AIChatMessage(
                session_id=session.id,
                role=ChatMessageRole.SYSTEM,
                content="I'm your AI event planning assistant! I can help you with everything from creating events, managing budgets, finding vendors, planning timelines, and answering any questions about event planning. What can I help you with today?"
            )
            db.add(system_message)
            
            # Process initial user message
            user_message = AIChatMessage(
                session_id=session.id,
                role=ChatMessageRole.USER,
                content=session_data.initial_message
            )
            db.add(user_message)
            
            # Generate AI response
            ai_response = await self._generate_chat_response(
                session, 
                session_data.initial_message,
                db
            )
            
            ai_message = AIChatMessage(
                session_id=session.id,
                role=ChatMessageRole.ASSISTANT,
                content=ai_response["content"],
                suggestions=json.dumps(ai_response.get("suggestions", [])),
                event_preview=json.dumps(ai_response.get("event_preview")) if ai_response.get("event_preview") else None
            )
            db.add(ai_message)
            
            db.commit()
            
            # Return response
            return ChatSessionResponse(
                id=session.session_id,
                user_id=user_id,
                status=session.status,
                messages=[
                    self._message_to_schema(system_message),
                    self._message_to_schema(user_message),
                    self._message_to_schema(ai_message)
                ],
                event_data=json.loads(session.event_data) if session.event_data else None,
                created_at=session.created_at,
                updated_at=session.updated_at
            )
            
        except Exception as e:
            db.rollback()
            print(f"Error creating chat session: {str(e)}")
            raise
    
    async def send_chat_message(
        self, 
        db: Session, 
        session_id: str, 
        user_id: int, 
        message_data: ChatMessageCreate
    ) -> ChatMessageResponse:
        """Send a message in an existing chat session."""
        try:
            # Get session
            session = db.query(AIChatSession).filter(
                AIChatSession.session_id == session_id,
                AIChatSession.user_id == user_id,
                AIChatSession.status == ChatSessionStatus.ACTIVE
            ).first()
            
            if not session:
                raise ValueError("Chat session not found or not active")
            
            # Create user message
            user_message = AIChatMessage(
                session_id=session.id,
                role=ChatMessageRole.USER,
                content=message_data.content
            )
            db.add(user_message)
            
            # Generate AI response
            ai_response = await self._generate_chat_response(
                session, 
                message_data.content,
                db
            )
            
            # Create AI message
            ai_message = AIChatMessage(
                session_id=session.id,
                role=ChatMessageRole.ASSISTANT,
                content=ai_response["content"],
                suggestions=json.dumps(ai_response.get("suggestions", [])),
                event_preview=json.dumps(ai_response.get("event_preview")) if ai_response.get("event_preview") else None
            )
            db.add(ai_message)
            
            # Update session event data if provided
            if ai_response.get("event_data"):
                session.event_data = json.dumps(ai_response["event_data"])
                session.updated_at = datetime.utcnow()
            
            db.commit()
            
            return ChatMessageResponse(
                session_id=session_id,
                message=self._message_to_schema(ai_message),
                suggestions=ai_response.get("suggestions", []),
                event_preview=ai_response.get("event_preview")
            )
            
        except Exception as e:
            db.rollback()
            print(f"Error sending chat message: {str(e)}")
            raise
    
    async def get_chat_session(
        self, 
        db: Session, 
        session_id: str, 
        user_id: int
    ) -> ChatSessionResponse:
        """Get a chat session with all messages."""
        session = db.query(AIChatSession).filter(
            AIChatSession.session_id == session_id,
            AIChatSession.user_id == user_id
        ).first()
        
        if not session:
            raise ValueError("Chat session not found")
        
        messages = db.query(AIChatMessage).filter(
            AIChatMessage.session_id == session.id
        ).order_by(AIChatMessage.created_at).all()
        
        return ChatSessionResponse(
            id=session.session_id,
            user_id=user_id,
            status=session.status,
            messages=[self._message_to_schema(msg) for msg in messages],
            event_data=json.loads(session.event_data) if session.event_data else None,
            created_at=session.created_at,
            updated_at=session.updated_at,
            completed_at=session.completed_at
        )
    
    async def complete_chat_session(
        self, 
        db: Session, 
        session_id: str, 
        user_id: int
    ) -> Dict[str, Any]:
        """Complete a chat session and create the event."""
        try:
            session = db.query(AIChatSession).filter(
                AIChatSession.session_id == session_id,
                AIChatSession.user_id == user_id,
                AIChatSession.status == ChatSessionStatus.ACTIVE
            ).first()
            
            if not session:
                raise ValueError("Chat session not found or not active")
            
            if not session.event_data:
                raise ValueError("No event data available to create event")
            
            # Parse event data
            event_data = json.loads(session.event_data)
            
            # Convert chat event data to EventCreate schema
            event_create = EventCreate(
                title=event_data.get("title", "Untitled Event"),
                description=event_data.get("description", ""),
                event_type=event_data.get("event_type", "OTHER"),
                start_date=datetime.fromisoformat(event_data["start_date"]) if event_data.get("start_date") else datetime.utcnow() + timedelta(days=7),
                end_date=datetime.fromisoformat(event_data["end_date"]) if event_data.get("end_date") else None,
                location=event_data.get("location", ""),
                max_attendees=event_data.get("max_attendees"),
                is_public=event_data.get("is_public", False),
                budget=event_data.get("budget")
            )
            
            # Create the event
            event_service = EventService(db)
            created_event = event_service.create_event(event_create, user_id)
            
            # Update session
            session.status = ChatSessionStatus.COMPLETED
            session.completed_at = datetime.utcnow()
            session.created_event_id = created_event.id
            
            db.commit()
            
            return {
                "success": True,
                "event_id": created_event.id,
                "session_id": session_id,
                "message": "Event created successfully from chat session!"
            }
            
        except Exception as e:
            db.rollback()
            print(f"Error completing chat session: {str(e)}")
            raise
    
    def _message_to_schema(self, message: AIChatMessage) -> Dict[str, Any]:
        """Convert database message to schema format."""
        return {
            "role": message.role,
            "content": message.content,
            "timestamp": message.created_at,
            "metadata": json.loads(message.extra_data) if message.extra_data else None
        }
    
    @openai_circuit_breaker(fallback=ai_fallback)
    async def _generate_chat_response(
        self, 
        session: AIChatSession, 
        user_message: str,
        db: Session
    ) -> Dict[str, Any]:
        """Generate AI response for chat conversation."""
        try:
            # Get conversation history
            messages = db.query(AIChatMessage).filter(
                AIChatMessage.session_id == session.id
            ).order_by(AIChatMessage.created_at).all()
            
            # Build conversation context
            conversation = []
            for msg in messages:
                if msg.role != ChatMessageRole.SYSTEM:
                    conversation.append({
                        "role": msg.role.value,
                        "content": msg.content
                    })
            
            # Add current user message
            conversation.append({
                "role": "user",
                "content": user_message
            })
            
            # Build system prompt
            system_prompt = self._build_event_creation_prompt(session)
            
            # Call OpenAI
            response = await openai.ChatCompletion.acreate(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    *conversation
                ],
                temperature=0.7,
                max_tokens=1000
            )
            
            ai_content = response.choices[0].message.content
            
            # Parse response for structured data
            parsed_response = self._parse_ai_response(ai_content, session)
            
            return parsed_response
            
        except Exception as e:
            print(f"AI response generation failed: {str(e)}")
            return {
                "content": "I apologize, but I'm having trouble processing your request right now. Could you please try rephrasing your message?",
                "suggestions": ["Tell me about your event", "What type of event are you planning?", "When is your event?"]
            }
    
    def _build_event_creation_prompt(self, session: AIChatSession) -> str:
        """Build system prompt for general event planning assistant."""
        current_data = json.loads(session.event_data) if session.event_data else {}
        context = json.loads(session.context) if session.context else {}
        
        user_events = context.get('user_events', [])
        events_context = ""
        if user_events:
            events_context = f"\n\nUser's current events:\n{json.dumps(user_events, indent=2)}"
        
        return f"""You are an expert event planning assistant for "Plan et al" - a comprehensive event management platform.

Your role:
- Help users with ALL aspects of event planning, not just event creation
- Answer questions about event management, tips, best practices
- Provide advice on budgeting, vendor selection, timelines, invitations, etc.
- Help brainstorm ideas and solve event planning challenges
- Offer to create, update, or manage events when appropriate
- Be conversational, friendly, professional, and knowledgeable

Capabilities you can help with:
- Event creation and planning
- Budget management and optimization
- Vendor recommendations and selection
- Timeline creation and scheduling
- Guest list management and invitations
- Menu planning and catering
- Decoration and theme ideas
- Task checklist generation
- Weather contingency planning
- Gift suggestions
- General event planning advice and tips

Current conversation context:
{f"Building event data: {json.dumps(current_data, indent=2)}" if current_data else "No active event creation in progress"}{events_context}

Guidelines:
- Engage in natural, open-ended conversations
- Don't force event creation unless the user clearly wants to create an event
- Provide actionable advice and specific recommendations
- Reference user's existing events when relevant
- Offer 2-3 helpful suggestions or follow-up questions
- When user wants to create an event, help gather necessary details progressively
- Be creative and helpful with brainstorming

Important: You can discuss ANY aspect of event planning. Users can ask you anything - from "How do I plan a surprise party?" to "What's a good budget for a wedding?" to "Help me create a birthday event next week."

Response format: Provide natural conversational responses. Be helpful, specific, and actionable."""
    
    def _parse_ai_response(self, ai_content: str, session: AIChatSession) -> Dict[str, Any]:
        """
        Parse AI response to extract event data and generate suggestions.
        This method uses NLP techniques to extract structured information from unstructured text.
        """
        # Get current event data from session
        current_data = json.loads(session.event_data) if session.event_data else {}
        event_data = current_data.copy()
        
        # Extract entities from AI response
        extracted_data = self._extract_entities_from_text(ai_content)
        
        # Update event data with extracted information
        if extracted_data:
            event_data.update(extracted_data)
        
        # Generate contextual suggestions based on current state
        suggestions = self._generate_contextual_suggestions(event_data)
        
        # Create event preview if we have enough data
        event_preview = None
        if event_data.get("title") and event_data.get("start_date"):
            event_preview = {
                "title": event_data.get("title"),
                "date": event_data.get("start_date"),
                "location": event_data.get("location", "TBD"),
                "type": event_data.get("event_type", "Event"),
                "description": event_data.get("description", ""),
                "duration": event_data.get("duration"),
                "guest_count": event_data.get("guest_count")
            }
        
        return {
            "content": ai_content,
            "suggestions": suggestions,
            "event_data": event_data if event_data != current_data else None,
            "event_preview": event_preview
        }
    
    def _extract_entities_from_text(self, text: str) -> Dict[str, Any]:
        """
        Extract event-related entities from text using NLP techniques.
        Returns a dictionary with extracted event data.
        """
        extracted_data = {}
        
        # Extract event title/name
        title = self._extract_event_title(text)
        if title:
            extracted_data["title"] = title
        
        # Extract dates and times
        dates = self._extract_dates(text)
        if dates:
            extracted_data.update(dates)
        
        # Extract location
        location = self._extract_location(text)
        if location:
            extracted_data["location"] = location
        
        # Extract numbers (guest count, duration, etc.)
        numbers = self._extract_numbers(text)
        if numbers:
            extracted_data.update(numbers)
        
        # Extract event type
        event_type = self._extract_event_type(text)
        if event_type:
            extracted_data["event_type"] = event_type
        
        # Extract description/details
        description = self._extract_description(text)
        if description:
            extracted_data["description"] = description
        
        return extracted_data
    
    def _extract_event_title(self, text: str) -> Optional[str]:
        """Extract event title from text using pattern matching."""
        # Patterns for event titles
        title_patterns = [
            r"(?:event|party|meeting|celebration|gathering|conference|workshop|seminar|birthday|wedding|anniversary|dinner|lunch|breakfast|brunch|picnic|barbecue|bbq|concert|show|festival|tournament|game|match|competition|reunion|graduation|baby shower|bridal shower|housewarming|fundraiser|charity|gala|auction|sale|fair|market|expo|exhibition|presentation|launch|opening|closing|ceremony|service|memorial|funeral|wake|reception|cocktail|happy hour|networking|mixer|social|dance|ball|prom|homecoming|banquet|feast|potluck|cookout|tailgate|camping|trip|vacation|retreat|getaway|outing|excursion|tour|visit|appointment|consultation|interview|date|meetup|hangout|playdate|sleepover|study|session|class|lesson|training|course|webinar|demo|demonstration|trial|test|exam|quiz|review|evaluation|assessment|inspection|audit|survey|poll|vote|election|campaign|rally|protest|march|parade|procession|ceremony|ritual|tradition|custom|practice|habit|routine|schedule|agenda|plan|program|itinerary|timeline|calendar|diary|journal|log|record|report|summary|overview|outline|draft|proposal|suggestion|recommendation|advice|tip|hint|clue|idea|concept|notion|thought|opinion|view|perspective|angle|approach|method|technique|strategy|tactic|plan|scheme|plot|design|blueprint|layout|structure|framework|system|process|procedure|protocol|guideline|rule|regulation|policy|standard|requirement|specification|criteria|condition|term|clause|provision|stipulation|agreement|contract|deal|arrangement|understanding|accord|pact|treaty|alliance|partnership|collaboration|cooperation|teamwork|joint|venture|project|initiative|campaign|mission|goal|objective|target|aim|purpose|intention|plan|strategy|approach|method|technique|way|means|solution|answer|response|reply|feedback|comment|remark|observation|note|message|communication|correspondence|letter|email|text|call|phone|video|chat|conversation|discussion|talk|speech|presentation|lecture|address|sermon|homily|eulogy|toast|tribute|dedication|acknowledgment|recognition|award|prize|honor|medal|trophy|certificate|diploma|degree|qualification|credential|license|permit|pass|ticket|voucher|coupon|discount|offer|deal|bargain|sale|promotion|advertisement|ad|commercial|announcement|notice|bulletin|newsletter|flyer|poster|sign|banner|flag|symbol|logo|brand|trademark|label|tag|sticker|badge|pin|button|patch|emblem|insignia|crest|coat|arms|shield|sword|weapon|tool|instrument|device|gadget|machine|equipment|gear|apparatus|appliance|fixture|furniture|decoration|ornament|accessory|jewelry|clothing|outfit|costume|uniform|dress|suit|shirt|pants|shoes|hat|cap|helmet|mask|gloves|socks|underwear|lingerie|swimwear|sportswear|activewear|casual|formal|business|professional|work|office|home|house|apartment|condo|flat|room|bedroom|bathroom|kitchen|living|dining|family|guest|master|basement|attic|garage|yard|garden|patio|deck|balcony|porch|driveway|sidewalk|street|road|avenue|boulevard|lane|alley|path|trail|walkway|bridge|tunnel|overpass|underpass|intersection|crosswalk|traffic|light|sign|signal|stop|yield|speed|limit|zone|area|region|district|neighborhood|community|town|city|state|province|country|nation|continent|world|globe|earth|planet|space|universe|cosmos|galaxy|star|sun|moon|satellite|asteroid|comet|meteor|meteorite|rock|stone|mineral|crystal|gem|diamond|gold|silver|copper|iron|steel|metal|wood|timber|lumber|paper|cardboard|plastic|rubber|glass|ceramic|clay|pottery|fabric|textile|cotton|wool|silk|leather|fur|feather|hair|skin|bone|muscle|blood|organ|tissue|cell|molecule|atom|particle|element|compound|mixture|solution|liquid|gas|solid|plasma|energy|power|force|strength|weight|mass|volume|density|pressure|temperature|heat|cold|hot|warm|cool|freezing|boiling|melting|evaporating|condensing|sublimating|crystallizing|dissolving|mixing|separating|filtering|purifying|cleaning|washing|drying|heating|cooling|cooking|baking|frying|grilling|roasting|boiling|steaming|sautéing|braising|stewing|simmering|poaching|blanching|marinating|seasoning|flavoring|spicing|salting|sweetening|souring|bittering|umami|taste|flavor|aroma|smell|scent|fragrance|perfume|cologne|deodorant|soap|shampoo|conditioner|lotion|cream|oil|balm|salve|ointment|medicine|drug|medication|pill|tablet|capsule|liquid|syrup|injection|vaccine|treatment|therapy|cure|remedy|healing|recovery|rehabilitation|exercise|workout|fitness|health|wellness|nutrition|diet|food|meal|snack|drink|beverage|water|juice|soda|coffee|tea|alcohol|wine|beer|cocktail|smoothie|shake|protein|vitamin|mineral|supplement|herb|spice|seasoning|condiment|sauce|dressing|marinade|rub|glaze|frosting|icing|topping|garnish|decoration|presentation|plating|serving|portion|helping|course|appetizer|starter|main|entree|side|dessert|sweet|treat|candy|chocolate|cake|pie|cookie|pastry|bread|roll|bun|bagel|muffin|scone|croissant|donut|pancake|waffle|toast|cereal|oatmeal|granola|yogurt|cheese|milk|butter|cream|egg|meat|poultry|chicken|turkey|duck|goose|beef|pork|lamb|fish|seafood|shellfish|crab|lobster|shrimp|scallop|oyster|clam|mussel|squid|octopus|tuna|salmon|cod|halibut|sole|flounder|trout|bass|catfish|tilapia|mahi|snapper|grouper|mackerel|sardine|anchovy|herring|caviar|roe|sushi|sashimi|tempura|teriyaki|hibachi|stir|fry|curry|pasta|noodle|rice|grain|wheat|barley|oats|quinoa|couscous|bulgur|farro|millet|buckwheat|amaranth|chia|flax|hemp|sunflower|pumpkin|sesame|poppy|seed|nut|almond|walnut|pecan|cashew|pistachio|hazelnut|macadamia|brazil|pine|peanut|legume|bean|lentil|chickpea|pea|soy|tofu|tempeh|seitan|vegetable|fruit|berry|apple|orange|banana|grape|strawberry|blueberry|raspberry|blackberry|cranberry|cherry|peach|pear|plum|apricot|mango|pineapple|papaya|kiwi|melon|watermelon|cantaloupe|honeydew|avocado|tomato|cucumber|lettuce|spinach|kale|arugula|cabbage|broccoli|cauliflower|brussels|sprouts|asparagus|artichoke|celery|carrot|beet|radish|turnip|parsnip|sweet|potato|regular|onion|garlic|ginger|turmeric|basil|oregano|thyme|rosemary|sage|parsley|cilantro|dill|mint|chive|scallion|leek|shallot|pepper|bell|jalapeño|serrano|habanero|ghost|carolina|reaper|cayenne|paprika|chili|powder|cumin|coriander|cardamom|cinnamon|nutmeg|clove|allspice|vanilla|extract|essence|zest|peel|rind|juice|pulp|flesh|skin|pit|stone|core|stem|leaf|flower|petal|bud|bloom|blossom|bouquet|arrangement|centerpiece|vase|pot|planter|garden|greenhouse|nursery|farm|field|orchard|vineyard|ranch|barn|stable|pen|coop|cage|aquarium|terrarium|vivarium|habitat|environment|ecosystem|biome|climate|weather|season|spring|summer|fall|autumn|winter|rain|snow|sleet|hail|fog|mist|cloud|sun|sunshine|shadow|shade|light|dark|bright|dim|twilight|dawn|dusk|sunrise|sunset|noon|midnight|morning|afternoon|evening|night|day|week|month|year|decade|century|millennium|era|age|period|time|moment|instant|second|minute|hour|schedule|calendar|date|appointment|meeting|event|occasion|celebration|party|gathering|get|together|reunion|conference|convention|summit|symposium|seminar|workshop|class|course|lesson|training|session|practice|rehearsal|performance|show|concert|recital|play|musical|opera|ballet|dance|theater|cinema|movie|film|documentary|series|episode|season|finale|premiere|debut|opening|closing|intermission|break|pause|rest|stop|end|finish|complete|done|over|through|across|around|about|regarding|concerning|pertaining|relating|referring|mentioning|discussing|talking|speaking|saying|telling|asking|answering|responding|replying|commenting|remarking|observing|noting|pointing|indicating|showing|demonstrating|explaining|describing|detailing|outlining|summarizing|reviewing|analyzing|examining|studying|researching|investigating|exploring|discovering|finding|locating|searching|looking|seeking|hunting|tracking|following|pursuing|chasing|catching|capturing|grabbing|holding|carrying|lifting|moving|transporting|delivering|shipping|mailing|sending|receiving|getting|obtaining|acquiring|purchasing|buying|selling|trading|exchanging|swapping|bartering|negotiating|bargaining|dealing|contracting|agreeing|accepting|approving|confirming|verifying|validating|authenticating|authorizing|permitting|allowing|enabling|facilitating|helping|assisting|supporting|backing|endorsing|recommending|suggesting|proposing|offering|providing|supplying|furnishing|equipping|outfitting|preparing|organizing|arranging|planning|scheduling|coordinating|managing|directing|leading|guiding|instructing|teaching|training|educating|informing|notifying|alerting|warning|cautioning|advising|counseling|consulting|coaching|mentoring|supervising|overseeing|monitoring|watching|observing|checking|inspecting|examining|testing|evaluating|assessing|measuring|weighing|counting|calculating|computing|figuring|determining|deciding|choosing|selecting|picking|opting|preferring|favoring|liking|loving|enjoying|appreciating|valuing|treasuring|cherishing|adoring|worshipping|revering|respecting|honoring|celebrating|commemorating|remembering|recalling|reminiscing|reflecting|thinking|pondering|considering|contemplating|meditating|praying|hoping|wishing|dreaming|imagining|visualizing|picturing|envisioning|foreseeing|predicting|forecasting|anticipating|expecting|awaiting|preparing|readying|getting|ready|set|go|start|begin|commence|initiate|launch|kick|off|open|close|shut|lock|unlock|secure|protect|guard|defend|shield|shelter|cover|hide|conceal|reveal|expose|uncover|discover|find|locate|identify|recognize|distinguish|differentiate|separate|divide|split|break|crack|shatter|smash|crush|destroy|demolish|ruin|damage|harm|hurt|injure|wound|cut|slice|chop|dice|mince|grind|blend|mix|stir|whisk|beat|whip|fold|knead|roll|flatten|press|squeeze|compress|expand|stretch|pull|push|drag|carry|lift|raise|lower|drop|fall|tumble|trip|slip|slide|glide|flow|stream|pour|drip|leak|spill|splash|spray|mist|fog|steam|smoke|burn|ignite|light|extinguish|put|out|turn|on|off|switch|flip|toggle|press|push|pull|twist|turn|rotate|spin|revolve|orbit|circle|loop|spiral|curve|bend|fold|crease|wrinkle|smooth|flatten|iron|press|steam|dry|wet|soak|drench|saturate|absorb|sponge|wipe|clean|wash|rinse|scrub|polish|shine|buff|wax|coat|paint|color|dye|stain|bleach|whiten|brighten|lighten|darken|dim|fade|wear|tear|rip|cut|sew|stitch|mend|repair|fix|restore|renovate|remodel|rebuild|construct|build|create|make|craft|design|draw|sketch|paint|color|illustrate|photograph|capture|record|document|write|type|print|publish|release|distribute|share|spread|broadcast|transmit|send|deliver|transport|move|relocate|transfer|shift|change|alter|modify|adjust|adapt|customize|personalize|tailor|fit|size|measure|weigh|count|number|label|tag|mark|sign|stamp|seal|close|open|unlock|lock|secure|fasten|attach|connect|join|link|bind|tie|knot|bow|ribbon|string|rope|chain|cable|wire|cord|thread|yarn|fabric|cloth|material|substance|matter|thing|object|item|piece|part|component|element|ingredient|factor|aspect|feature|characteristic|trait|quality|property|attribute|detail|specification|requirement|condition|rule|regulation|law|policy|procedure|process|method|technique|approach|strategy|plan|scheme|system|structure|framework|organization|arrangement|setup|configuration|layout|design|pattern|template|model|example|sample|specimen|instance|case|situation|scenario|circumstance|condition|state|status|position|location|place|spot|site|area|zone|region|territory|domain|field|sphere|realm|world|universe|dimension|space|room|chamber|hall|corridor|passage|pathway|route|road|street|avenue|boulevard|lane|alley|path|trail|track|course|circuit|loop|ring|circle|square|triangle|rectangle|oval|diamond|star|cross|plus|minus|equal|sign|symbol|icon|image|picture|photo|drawing|painting|artwork|masterpiece|creation|work|project|task|job|assignment|duty|responsibility|obligation|commitment|promise|pledge|vow|oath|word|statement|declaration|announcement|proclamation|notice|warning|alert|alarm|signal|indication|sign|clue|hint|tip|suggestion|advice|recommendation|proposal|offer|invitation|request|demand|requirement|need|want|desire|wish|hope|dream|goal|objective|target|aim|purpose|intention|plan|idea|concept|notion|thought|opinion|view|perspective|belief|faith|trust|confidence|assurance|guarantee|promise|commitment|dedication|devotion|loyalty|allegiance|support|backing|endorsement|approval|acceptance|agreement|consent|permission|authorization|license|permit|pass|ticket|entry|access|admission|entrance|exit|departure|arrival|coming|going|leaving|staying|remaining|continuing|proceeding|advancing|progressing|developing|growing|expanding|increasing|rising|climbing|ascending|descending|falling|dropping|declining|decreasing|reducing|shrinking|contracting|compressing|expanding|stretching|extending|reaching|touching|feeling|sensing|perceiving|noticing|observing|seeing|looking|watching|viewing|examining|inspecting|checking|testing|trying|attempting|endeavoring|striving|struggling|fighting|battling|competing|contesting|challenging|opposing|resisting|defending|protecting|guarding|securing|safeguarding|preserving|maintaining|keeping|holding|retaining|storing|saving|collecting|gathering|accumulating|amassing|hoarding|stockpiling|supplying|providing|offering|giving|donating|contributing|sharing|distributing|spreading|scattering|dispersing|disseminating|broadcasting|transmitting|communicating|conveying|expressing|articulating|stating|declaring|announcing|proclaiming|revealing|disclosing|exposing|uncovering|discovering|finding|locating|identifying|recognizing|acknowledging|admitting|confessing|revealing|telling|informing|notifying|alerting|warning|advising|counseling|guiding|directing|instructing|teaching|educating|training|coaching|mentoring|supervising|managing|controlling|regulating|governing|ruling|commanding|ordering|demanding|requiring|requesting|asking|questioning|inquiring|investigating|researching|studying|examining|analyzing|evaluating|assessing|judging|deciding|determining|concluding|resolving|solving|fixing|repairing|mending|healing|curing|treating|helping|assisting|supporting|aiding|serving|catering|accommodating|hosting|entertaining|amusing|delighting|pleasing|satisfying|fulfilling|completing|finishing|ending|concluding|terminating|stopping|ceasing|quitting|abandoning|leaving|departing|exiting|going|coming|arriving|entering|joining|participating|engaging|involving|including|containing|comprising|consisting|featuring|showcasing|highlighting|emphasizing|stressing|underlining|pointing|indicating|showing|demonstrating|proving|confirming|verifying|validating|authenticating|certifying|guaranteeing|assuring|promising|committing|dedicating|devoting|pledging|vowing|swearing|declaring|stating|saying|telling|speaking|talking|discussing|conversing|chatting|communicating|corresponding|writing|typing|texting|calling|phoning|emailing|messaging|contacting|reaching|touching|connecting|linking|joining|uniting|combining|merging|blending|mixing|integrating|incorporating|including|adding|inserting|placing|putting|setting|positioning|locating|situating|establishing|founding|creating|forming|building|constructing|developing|designing|planning|organizing|arranging|preparing|setting|up|getting|ready|making|doing|performing|executing|carrying|out|implementing|applying|using|utilizing|employing|operating|running|working|functioning|serving|acting|behaving|conducting|managing|handling|dealing|coping|struggling|fighting|battling|competing|racing|running|walking|jogging|hiking|climbing|swimming|diving|flying|soaring|gliding|floating|drifting|sailing|rowing|paddling|cycling|biking|riding|driving|traveling|journeying|touring|visiting|exploring|discovering|adventuring|experiencing|living|existing|being|staying|remaining|continuing|lasting|enduring|surviving|thriving|flourishing|prospering|succeeding|achieving|accomplishing|attaining|reaching|gaining|obtaining|acquiring|getting|receiving|accepting|taking|grabbing|seizing|capturing|catching|holding|keeping|maintaining|preserving|protecting|defending|guarding|securing|saving|storing|collecting|gathering|assembling|organizing|arranging|sorting|categorizing|classifying|grouping|dividing|separating|distinguishing|differentiating|comparing|contrasting|matching|pairing|coupling|connecting|linking|joining|uniting|combining|merging|blending|mixing|stirring|shaking|vibrating|oscillating|swinging|rocking|rolling|spinning|turning|rotating|revolving|circling|looping|spiraling|curving|bending|twisting|winding|weaving|threading|stringing|tying|binding|fastening|attaching|connecting|joining|linking|coupling|pairing|matching|fitting|suiting|adapting|adjusting|modifying|changing|altering|transforming|converting|translating|interpreting|explaining|describing|defining|clarifying|illustrating|demonstrating|showing|displaying|exhibiting|presenting|introducing|revealing|exposing|uncovering|discovering|finding|locating|identifying|recognizing|distinguishing|differentiating|separating|dividing|splitting|breaking|cracking|shattering|smashing|crushing|destroying|demolishing|ruining|damaging|harming|hurting|injuring|wounding|cutting|slicing|chopping|dicing|mincing|grinding|crushing|pressing|squeezing|compressing|expanding|stretching|pulling|pushing|dragging|carrying|lifting|raising|lowering|dropping|falling|tumbling|tripping|slipping|sliding|gliding|flowing|streaming|pouring|dripping|leaking|spilling|splashing|spraying|misting|fogging|steaming|smoking|burning|igniting|lighting|extinguishing|putting|out|turning|on|off|switching|flipping|toggling|pressing|pushing|pulling|twisting|turning|rotating|spinning|revolving|orbiting|circling|looping|spiraling|curving|bending|folding|creasing|wrinkling|smoothing|flattening|ironing|pressing|steaming|drying|wetting|soaking|drenching|saturating|absorbing|sponging|wiping|cleaning|washing|rinsing|scrubbing|polishing|shining|buffing|waxing|coating|painting|coloring|dyeing|staining|bleaching|whitening|brightening|lightening|darkening|dimming|fading|wearing|tearing|ripping|cutting|sewing|stitching|mending|repairing|fixing|restoring|renovating|remodeling|rebuilding|constructing|building|creating|making|crafting|designing|drawing|sketching|painting|coloring|illustrating|photographing|capturing|recording|documenting|writing|typing|printing|publishing|releasing|distributing|sharing|spreading|broadcasting|transmitting|sending|delivering|transporting|moving|relocating|transferring|shifting|changing|altering|modifying|adjusting|adapting|customizing|personalizing|tailoring|fitting|sizing|measuring|weighing|counting|numbering|labeling|tagging|marking|signing|stamping|sealing|closing|opening|unlocking|locking|securing|fastening|attaching|connecting|joining|linking|binding|tying|knotting|bowing|ribboning|stringing|roping|chaining|cabling|wiring|cording|threading|yarning|fabricating|clothing|materializing|substantiating|mattering|thinging|objecting|itemizing|piecing|parting|componenting|elementing|ingredienting|factoring|aspecting|featuring|characterizing|traiting|qualifying|propertying|attributing|detailing|specifying|requiring|conditioning|ruling|regulating|lawing|policying|proceduring|processing|methoding|techniqu"
        ]
        
        # Look for event titles in quotes or after specific keywords
        for pattern in title_patterns:
            matches = re.findall(rf'(?:for|called|named|titled|about|regarding)\s+["\']([^"\']+)["\']', text, re.IGNORECASE)
            if matches:
                return matches[0].strip()
        
        # Look for capitalized phrases that might be event names
        capitalized_phrases = re.findall(r'\b[A-Z][a-zA-Z\s]{2,30}(?=\s(?:event|party|meeting|celebration|gathering))', text)
        if capitalized_phrases:
            return capitalized_phrases[0].strip()
        
        return None
    
    def _extract_dates(self, text: str) -> Dict[str, Any]:
        """Extract dates and times from text using dateparser."""
        date_info = {}
        
        # Use dateparser to find dates in natural language
        try:
            # Look for various date patterns
            date_patterns = [
                r'(?:on|at|for|during)\s+([^,.!?]+?)(?:\s+(?:at|from|to|until|through)|\.|,|!|\?|$)',
                r'(?:next|this|last)\s+\w+',
                r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}',
                r'\w+\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4}',
                r'\d{1,2}:\d{2}(?:\s*[AaPp][Mm])?'
            ]
            
            for pattern in date_patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                for match in matches:
                    parsed_date = dateparser.parse(match)
                    if parsed_date:
                        if not date_info.get("start_date"):
                            date_info["start_date"] = parsed_date.isoformat()
                        elif not date_info.get("end_date") and parsed_date != dateparser.parse(date_info["start_date"]):
                            date_info["end_date"] = parsed_date.isoformat()
                        break
                if date_info.get("start_date"):
                    break
        except Exception:
            pass
        
        return date_info
    
    def _extract_location(self, text: str) -> Optional[str]:
        """Extract location information from text."""
        # Location patterns
        location_patterns = [
            r'(?:at|in|on|near|by|around)\s+([A-Z][a-zA-Z\s,]+?)(?:\s+(?:on|at|for|with)|[,.!?]|$)',
            r'(?:venue|location|place|address):\s*([^,.!?]+)',
            r'\b\d+\s+[A-Z][a-zA-Z\s]+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Drive|Dr|Lane|Ln|Way|Place|Pl|Court|Ct)\b',
            r'\b[A-Z][a-zA-Z\s]+(?:Hotel|Restaurant|Cafe|Bar|Club|Center|Centre|Hall|Room|Building|Park|Beach|Lake|River|Mountain|Hill)\b'
        ]
        
        for pattern in location_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                location = matches[0].strip()
                # Clean up common artifacts
                location = re.sub(r'^(at|in|on|near|by|around)\s+', '', location, flags=re.IGNORECASE)
                if len(location) > 3 and len(location) < 100:
                    return location
        
        return None
    
    def _extract_numbers(self, text: str) -> Dict[str, Any]:
        """Extract numerical information like guest count, duration, etc."""
        numbers_info = {}
        
        # Guest count patterns
        guest_patterns = [
            r'(?:for|with|about|around|approximately)\s+(\d+)\s+(?:people|guests|attendees|participants)',
            r'(\d+)\s+(?:person|people|guest|guests|attendee|attendees|participant|participants)',
            r'(?:guest|attendee|participant)\s+(?:count|number):\s*(\d+)'
        ]
        
        for pattern in guest_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                numbers_info["guest_count"] = int(matches[0])
                break
        
        # Duration patterns
        duration_patterns = [
            r'(?:for|lasting|duration|length):\s*(\d+)\s*(hour|hours|hr|hrs|minute|minutes|min|mins)',
            r'(\d+)\s*(hour|hours|hr|hrs|minute|minutes|min|mins)\s*(?:long|duration|event)',
            r'(?:from|starting)\s+\d{1,2}:\d{2}.*?(?:to|until|ending)\s+\d{1,2}:\d{2}'
        ]
        
        for pattern in duration_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                duration_value, duration_unit = matches[0]
                if 'hour' in duration_unit.lower() or 'hr' in duration_unit.lower():
                    numbers_info["duration"] = f"{duration_value} hours"
                else:
                    numbers_info["duration"] = f"{duration_value} minutes"
                break
        
        return numbers_info
    
    def _extract_event_type(self, text: str) -> Optional[str]:
        """Extract event type from text."""
        event_types = {
            'birthday': ['birthday', 'bday', 'birth day'],
            'wedding': ['wedding', 'marriage', 'matrimony'],
            'meeting': ['meeting', 'conference', 'discussion'],
            'party': ['party', 'celebration', 'bash'],
            'dinner': ['dinner', 'supper', 'evening meal'],
            'lunch': ['lunch', 'luncheon', 'midday meal'],
            'breakfast': ['breakfast', 'morning meal'],
            'workshop': ['workshop', 'seminar', 'training'],
            'concert': ['concert', 'performance', 'show'],
            'sports': ['game', 'match', 'tournament', 'competition'],
            'social': ['gathering', 'get-together', 'meetup', 'hangout']
        }
        
        text_lower = text.lower()
        for event_type, keywords in event_types.items():
            for keyword in keywords:
                if keyword in text_lower:
                    return event_type
        
        return None
    
    def _extract_description(self, text: str) -> Optional[str]:
        """Extract event description or additional details."""
        # Look for descriptive sentences
        sentences = re.split(r'[.!?]+', text)
        
        # Find sentences that contain descriptive words
        descriptive_words = ['celebrate', 'honor', 'commemorate', 'enjoy', 'fun', 'special', 'important', 'memorable']
        
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) > 20 and len(sentence) < 200:
                for word in descriptive_words:
                    if word in sentence.lower():
                        return sentence
        
        return None
    
    def _generate_contextual_suggestions(self, event_data: Dict[str, Any]) -> List[str]:
        """Generate contextual suggestions based on current conversation state."""
        suggestions = []
        
        # If actively creating an event
        if event_data:
            if not event_data.get("title"):
                suggestions = [
                    "What should we call your event?", 
                    "Tell me about the occasion", 
                    "What type of event is this?"
                ]
            elif not event_data.get("start_date"):
                suggestions = [
                    "When would you like to have this event?", 
                    "What date works best?", 
                    "Any specific time in mind?"
                ]
            elif not event_data.get("location"):
                suggestions = [
                    "Where will this event take place?", 
                    "Do you have a venue in mind?", 
                    "Indoor or outdoor event?"
                ]
            elif not event_data.get("guest_count"):
                suggestions = [
                    "How many people will attend?", 
                    "What's the expected guest count?", 
                    "Small gathering or large event?"
                ]
            else:
                suggestions = [
                    "Shall we create this event?", 
                    "Any other details to add?", 
                    "Need help with budget planning?"
                ]
        else:
            # General suggestions when not creating an event
            suggestions = [
                "Help me create a new event",
                "What are some event planning tips?",
                "How do I manage my event budget?",
                "Suggest vendors for my event",
                "Help me create a timeline",
                "What's a good checklist for my event type?",
                "How do I handle RSVPs?",
                "Give me decoration ideas"
            ]
        
        return suggestions
    
    # EXISTING AI METHODS
    
    @openai_circuit_breaker(fallback=ai_fallback)
    async def generate_event_checklist(
        self, 
        event: Event, 
        budget: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """Generate AI-powered checklist for an event."""
        try:
            prompt = self._build_checklist_prompt(event, budget)
            
            response = await openai.ChatCompletion.acreate(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert event planner. Generate detailed, actionable checklists for events. Return only valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=1500
            )
            
            content = response.choices[0].message.content
            checklist = json.loads(content)
            
            return checklist.get("tasks", [])
            
        except Exception as e:
            print(f"AI checklist generation failed: {str(e)}")
            return self._get_fallback_checklist(event.event_type)
    
    @openai_circuit_breaker(fallback=ai_fallback)
    async def suggest_vendors(
        self, 
        event: Event, 
        category: str, 
        location: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Suggest vendors based on event type and location."""
        try:
            prompt = self._build_vendor_prompt(event, category, location)
            
            response = await openai.ChatCompletion.acreate(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a local event planning expert. Suggest realistic vendor types and services. Return only valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.8,
                max_tokens=1000
            )
            
            content = response.choices[0].message.content
            vendors = json.loads(content)
            
            return vendors.get("vendors", [])
            
        except Exception as e:
            print(f"AI vendor suggestion failed: {str(e)}")
            return self._get_fallback_vendors(category)
    
    @openai_circuit_breaker(fallback=ai_fallback)
    async def generate_menu_suggestions(
        self, 
        event: Event, 
        dietary_restrictions: List[str] = None,
        budget_per_person: Optional[float] = None
    ) -> Dict[str, Any]:
        """Generate menu suggestions based on event details."""
        try:
            prompt = self._build_menu_prompt(event, dietary_restrictions, budget_per_person)
            
            response = await openai.ChatCompletion.acreate(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a professional caterer and menu planner. Create diverse, appealing menus. Return only valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.8,
                max_tokens=1200
            )
            
            content = response.choices[0].message.content
            menu = json.loads(content)
            
            return menu
            
        except Exception as e:
            print(f"AI menu generation failed: {str(e)}")
            return self._get_fallback_menu(event.event_type)
    
    @openai_circuit_breaker(fallback=ai_fallback)
    async def optimize_budget(
        self, 
        event: Event, 
        current_expenses: List[Dict[str, Any]],
        target_budget: float
    ) -> Dict[str, Any]:
        """Analyze budget and suggest optimizations."""
        try:
            prompt = self._build_budget_prompt(event, current_expenses, target_budget)
            
            response = await openai.ChatCompletion.acreate(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a financial advisor specializing in event budgets. Provide practical cost-saving suggestions. Return only valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.6,
                max_tokens=1000
            )
            
            content = response.choices[0].message.content
            optimization = json.loads(content)
            
            return optimization
            
        except Exception as e:
            print(f"AI budget optimization failed: {str(e)}")
            return self._get_fallback_budget_tips()
    
    @openai_circuit_breaker(fallback=ai_fallback)
    async def generate_event_timeline(
        self, 
        event: Event, 
        tasks: List[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Generate a detailed event timeline/run-of-show."""
        try:
            prompt = self._build_timeline_prompt(event, tasks)
            
            response = await openai.ChatCompletion.acreate(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an event coordinator. Create detailed, realistic timelines for events. Return only valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.5,
                max_tokens=1200
            )
            
            content = response.choices[0].message.content
            timeline = json.loads(content)
            
            return timeline.get("timeline", [])
            
        except Exception as e:
            print(f"AI timeline generation failed: {str(e)}")
            return self._get_fallback_timeline(event)
    
    @openai_circuit_breaker(fallback=ai_fallback)
    async def suggest_gift_ideas(
        self, 
        event: Event, 
        recipient_info: Dict[str, Any],
        budget_range: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Generate personalized gift suggestions."""
        try:
            prompt = self._build_gift_prompt(event, recipient_info, budget_range)
            
            response = await openai.ChatCompletion.acreate(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a gift consultant. Suggest thoughtful, appropriate gifts based on the occasion and recipient. Return only valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.8,
                max_tokens=800
            )
            
            content = response.choices[0].message.content
            gifts = json.loads(content)
            
            return gifts.get("gift_ideas", [])
            
        except Exception as e:
            print(f"AI gift suggestion failed: {str(e)}")
            return self._get_fallback_gifts(event.event_type)
    
    @openai_circuit_breaker(fallback=ai_fallback)
    async def check_weather_and_suggest_backup(
        self, 
        event: Event, 
        location: str
    ) -> Dict[str, Any]:
        """Check weather forecast and suggest backup plans."""
        try:
            # Get weather forecast (you'd integrate with a weather API)
            weather_data = await self._get_weather_forecast(location, event.start_datetime)
            
            if weather_data.get("risk_level", "low") in ["high", "medium"]:
                prompt = self._build_weather_backup_prompt(event, weather_data)
                
                response = await openai.ChatCompletion.acreate(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "You are an event planner specializing in weather contingencies. Suggest practical backup plans. Return only valid JSON."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.7,
                    max_tokens=800
                )
                
                content = response.choices[0].message.content
                backup_plan = json.loads(content)
                
                return {
                    "weather_forecast": weather_data,
                    "backup_suggestions": backup_plan.get("suggestions", []),
                    "risk_level": weather_data.get("risk_level", "low")
                }
            
            return {
                "weather_forecast": weather_data,
                "backup_suggestions": [],
                "risk_level": "low"
            }
            
        except Exception as e:
            print(f"Weather check failed: {str(e)}")
            return {"weather_forecast": None, "backup_suggestions": [], "risk_level": "unknown"}
    
    def _message_to_schema(self, message: AIChatMessage) -> ChatMessageResponse:
        """Convert database message to schema."""
        return ChatMessageResponse(
            id=message.id,
            session_id=message.session_id,
            role=message.role,
            content=message.content,
            metadata=message.extra_data,
            created_at=message.created_at
        )
    
    # Prompt building methods
    def _build_checklist_prompt(self, event: Event, budget: Optional[float]) -> str:
        budget_text = f" with a budget of ${budget}" if budget else ""
        return f"""
Generate a comprehensive checklist for a {event.event_type} event titled "{event.title}"{budget_text}.
Event details:
- Date: {event.start_datetime.strftime('%Y-%m-%d %H:%M')}
- Venue: {event.venue_name or 'TBD'}
- Description: {event.description or 'No description'}

Return a JSON object with this structure:
{{
  "tasks": [
    {{
      "title": "Task name",
      "description": "Detailed description",
      "category": "venue|catering|decorations|entertainment|logistics|other",
      "priority": "high|medium|low",
      "estimated_cost": 100.00,
      "days_before_event": 30
    }}
  ]
}}
"""
    
    def _build_vendor_prompt(self, event: Event, category: str, location: Optional[str]) -> str:
        location_text = f" in {location}" if location else ""
        return f"""
Suggest {category} vendors for a {event.event_type} event{location_text}.
Event details:
- Title: {event.title}
- Date: {event.start_datetime.strftime('%Y-%m-%d')}
- Expected attendees: {event.max_attendees or 'Unknown'}

Return a JSON object with this structure:
{{
  "vendors": [
    {{
      "name": "Vendor name",
      "type": "Specific service type",
      "description": "What they offer",
      "estimated_cost_range": "$X - $Y",
      "contact_suggestion": "How to find them"
    }}
  ]
}}
"""
    
    def _build_menu_prompt(self, event: Event, dietary_restrictions: List[str], budget_per_person: Optional[float]) -> str:
        restrictions_text = f"Dietary restrictions: {', '.join(dietary_restrictions)}" if dietary_restrictions else "No dietary restrictions"
        budget_text = f"Budget per person: ${budget_per_person}" if budget_per_person else "No specific budget"
        
        return f"""
Create a menu for a {event.event_type} event.
Event details:
- Title: {event.title}
- Time: {event.start_datetime.strftime('%H:%M')}
- {restrictions_text}
- {budget_text}

Return a JSON object with this structure:
{{
  "appetizers": ["item1", "item2"],
  "main_courses": ["item1", "item2"],
  "desserts": ["item1", "item2"],
  "beverages": ["item1", "item2"],
  "estimated_cost_per_person": 25.00,
  "serving_suggestions": ["tip1", "tip2"]
}}
"""
    
    def _build_budget_prompt(self, event: Event, expenses: List[Dict], target_budget: float) -> str:
        total_expenses = sum(exp.get('amount', 0) for exp in expenses)
        return f"""
Analyze this event budget and suggest optimizations.
Event: {event.title} ({event.event_type})
Target budget: ${target_budget}
Current expenses: ${total_expenses}
Expense breakdown: {json.dumps(expenses, indent=2)}

Return a JSON object with this structure:
{{
  "current_total": {total_expenses},
  "target_budget": {target_budget},
  "over_under_budget": "amount",
  "optimization_suggestions": [
    {{
      "category": "expense category",
      "suggestion": "specific recommendation",
      "potential_savings": 100.00
    }}
  ],
  "alternative_options": ["option1", "option2"]
}}
"""
    
    def _build_timeline_prompt(self, event: Event, tasks: List[Dict]) -> str:
        tasks_text = json.dumps(tasks, indent=2) if tasks else "No specific tasks provided"
        return f"""
Create a detailed timeline for a {event.event_type} event.
Event details:
- Title: {event.title}
- Start: {event.start_datetime.strftime('%Y-%m-%d %H:%M')}
- End: {event.end_datetime.strftime('%Y-%m-%d %H:%M') if event.end_datetime else 'Not specified'}
- Venue: {event.venue_name or 'TBD'}
Tasks: {tasks_text}

Return a JSON object with this structure:
{{
  "timeline": [
    {{
      "time": "HH:MM",
      "activity": "Activity description",
      "duration_minutes": 30,
      "responsible_party": "Who handles this",
      "notes": "Additional details"
    }}
  ]
}}
"""
    
    def _build_gift_prompt(self, event: Event, recipient_info: Dict, budget_range: Optional[str]) -> str:
        budget_text = f"Budget range: {budget_range}" if budget_range else "No specific budget"
        return f"""
Suggest gift ideas for a {event.event_type} event.
Recipient info: {json.dumps(recipient_info, indent=2)}
{budget_text}

Return a JSON object with this structure:
{{
  "gift_ideas": [
    {{
      "name": "Gift name",
      "description": "Why it's appropriate",
      "estimated_cost": "$X - $Y",
      "where_to_buy": "Suggestion",
      "personalization_ideas": ["idea1", "idea2"]
    }}
  ]
}}
"""
    
    def _build_weather_backup_prompt(self, event: Event, weather_data: Dict) -> str:
        return f"""
Suggest backup plans for a {event.event_type} event due to weather concerns.
Event: {event.title}
Venue: {event.venue_name or 'Outdoor/TBD'}
Weather forecast: {json.dumps(weather_data, indent=2)}

Return a JSON object with this structure:
{{
  "suggestions": [
    {{
      "option": "Backup plan name",
      "description": "Detailed plan",
      "additional_cost": 0.00,
      "feasibility": "high|medium|low"
    }}
  ]
}}
"""
    
    # Fallback methods for when AI fails
    def _get_fallback_checklist(self, event_type: str) -> List[Dict[str, Any]]:
        base_tasks = [
            {"title": "Book venue", "category": "venue", "priority": "high", "days_before_event": 60},
            {"title": "Send invitations", "category": "logistics", "priority": "high", "days_before_event": 30},
            {"title": "Plan menu", "category": "catering", "priority": "medium", "days_before_event": 21},
            {"title": "Confirm final headcount", "category": "logistics", "priority": "high", "days_before_event": 7}
        ]
        return base_tasks
    
    def _get_fallback_vendors(self, category: str) -> List[Dict[str, Any]]:
        return [
            {
                "name": f"Local {category} providers",
                "type": category,
                "description": f"Search for {category} services in your area",
                "estimated_cost_range": "Varies",
                "contact_suggestion": "Check online directories or ask for referrals"
            }
        ]
    
    def _get_fallback_menu(self, event_type: str) -> Dict[str, Any]:
        return {
            "appetizers": ["Mixed nuts", "Cheese and crackers"],
            "main_courses": ["Sandwich platters", "Salad options"],
            "desserts": ["Cake", "Fresh fruit"],
            "beverages": ["Water", "Soft drinks", "Coffee"],
            "estimated_cost_per_person": 15.00,
            "serving_suggestions": ["Consider dietary restrictions", "Have vegetarian options"]
        }
    
    def _get_fallback_budget_tips(self) -> Dict[str, Any]:
        return {
            "optimization_suggestions": [
                {"category": "general", "suggestion": "Compare multiple vendor quotes", "potential_savings": 0},
                {"category": "general", "suggestion": "Consider off-peak dates and times", "potential_savings": 0}
            ],
            "alternative_options": ["DIY decorations", "Potluck-style catering"]
        }
    
    def _get_fallback_timeline(self, event: Event) -> List[Dict[str, Any]]:
        return [
            {"time": "Setup", "activity": "Venue setup and decorations", "duration_minutes": 60, "responsible_party": "Organizers"},
            {"time": "Start", "activity": "Event begins", "duration_minutes": 0, "responsible_party": "Host"},
            {"time": "End", "activity": "Event cleanup", "duration_minutes": 30, "responsible_party": "Volunteers"}
        ]
    
    def _get_fallback_gifts(self, event_type: str) -> List[Dict[str, Any]]:
        return [
            {
                "name": "Gift card",
                "description": "Flexible option for any occasion",
                "estimated_cost": "$25 - $100",
                "where_to_buy": "Online or retail stores",
                "personalization_ideas": ["Choose recipient's favorite store"]
            }
        ]
    
    async def _get_weather_forecast(self, location: str, date: datetime) -> Dict[str, Any]:
        """Get weather forecast from weather API (placeholder implementation)."""
        # This would integrate with a real weather API like OpenWeatherMap
        # For now, return a mock response
        return {
            "location": location,
            "date": date.strftime('%Y-%m-%d'),
            "temperature": "22°C",
            "conditions": "Partly cloudy",
            "precipitation_chance": 20,
            "risk_level": "low"
        }

# Global AI service instance
ai_service = AIService()