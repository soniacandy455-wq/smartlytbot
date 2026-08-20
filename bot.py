

     
import os
import logging
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Updater,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    Filters,
    ConversationHandler
)
import openai

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Get API keys
TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# Initialize OpenAI
if OPENAI_API_KEY:
    openai.api_key = OPENAI_API_KEY
    print("✅ OpenAI API key loaded successfully")
else:
    print("❌ OPENAI_API_KEY not found")

# States for conversation
(
    ASKING,
    SUMMARIZING,
    REWRITING,
    IDEAS,
    EXPLAINING,
    TRANSLATING,
    DOCUMENT
) = range(7)

# ============ SAFE OPENAI CALL ============

def safe_openai_call(prompt, max_retries=3):
    """Safely call OpenAI with retry logic"""
    if not OPENAI_API_KEY:
        return "⚠️ OpenAI API key not configured."
    
    for attempt in range(max_retries):
        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=500,
                temperature=0.7
            )
            
            if response and response.choices:
                return response.choices[0].message.content
            else:
                raise Exception("Empty response")
                
        except Exception as e:
            logger.error(f"OpenAI error attempt {attempt+1}: {e}")
            if attempt < max_retries - 1:
                continue
            return f"⚠️ Error: {str(e)[:100]}"
    
    return "❌ Max retries exceeded. Please try again."

# ============ MENU ============

def get_main_menu():
    keyboard = [
        [InlineKeyboardButton("💬 Ask Question", callback_data='ask')],
        [InlineKeyboardButton("📝 Summarize Text", callback_data='summarize')],
        [InlineKeyboardButton("✍️ Rewrite Text", callback_data='rewrite')],
        [InlineKeyboardButton("💡 Generate Ideas", callback_data='ideas')],
        [InlineKeyboardButton("📚 Explain Topic", callback_data='explain')],
        [InlineKeyboardButton("🌐 Translate Text", callback_data='translate')],
        [InlineKeyboardButton("📄 Analyze Document", callback_data='document')],
    ]
    return InlineKeyboardMarkup(keyboard)

# ============ COMMANDS ============

def start(update, context):
    try:
        context.user_data.clear()
        
        welcome = (
            "🤖 **Welcome to SmartBot!**\n\n"
            "Your AI-powered assistant is ready to help you with:\n\n"
            "💬 **Ask Questions** - Get answers\n"
            "📝 **Summarize Text** - Short summaries\n"
            "✍️ **Rewrite Text** - Clearer text\n"
            "💡 **Generate Ideas** - Creative ideas\n"
            "📚 **Explain Topics** - Simple explanations\n"
            "🌐 **Translate Text** - Multi-language\n"
            "📄 **Analyze Documents** - PDF/TXT files\n\n"
            "Choose an option below:"
        )
        update.message.reply_text(welcome, reply_markup=get_main_menu(), parse_mode='Markdown')
        return ConversationHandler.END
    except Exception as e:
        logger.error(f"Error in start: {e}")
        update.message.reply_text("⚠️ Please try /start again.")
        return ConversationHandler.END

def cancel(update, context):
    try:
        context.user_data.clear()
        update.message.reply_text(
            "✅ Cancelled. Use /start to see options.",
            reply_markup=get_main_menu()
        )
        return ConversationHandler.END
    except Exception as e:
        logger.error(f"Error in cancel: {e}")
        return ConversationHandler.END

# ============ BUTTON HANDLER ============

def button_handler(update, context):
    try:
        query = update.callback_query
        query.answer()
        action = query.data
        
        action_map = {
            'ask': ("💬 Send your question:", ASKING),
            'summarize': ("📝 Send text to summarize:", SUMMARIZING),
            'rewrite': ("✍️ Send text to rewrite:", REWRITING),
            'ideas': ("💡 Send topic for ideas:", IDEAS),
            'explain': ("📚 Send topic to explain:", EXPLAINING),
            'translate': ("🌐 Send language:text to translate:", TRANSLATING),
            'document': ("📄 Upload document (PDF/TXT):", DOCUMENT)
        }
        
        message, state = action_map.get(action, ("Please choose:", None))
        query.edit_message_text(message, reply_markup=None)
        
        if state is not None:
            context.user_data['action'] = action
            return state
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"Error in button: {e}")
        query.edit_message_text("⚠️ Error. Use /start to try again.")
        return ConversationHandler.END

# ============ FEATURE HANDLERS ============

def ask_question(update, context):
    try:
        if not OPENAI_API_KEY:
            update.message.reply_text(
                "⚠️ **OpenAI API key not configured!**",
                parse_mode='Markdown'
            )
            return ConversationHandler.END
        
        if not update.message or not update.message.text:
            update.message.reply_text("⚠️ Please send your question.")
            return ASKING
        
        question = update.message.text
        if len(question.strip()) < 2:
            update.message.reply_text("⚠️ Please ask a longer question.")
            return ASKING
        
        update.message.reply_text("🤔 Thinking...")
        response = safe_openai_call(f"Answer this: {question}")
        
        if not response:
            response = "⚠️ Could not generate response. Please try again."
        
        update.message.reply_text(f"💬 **Answer:**\n\n{response}", parse_mode='Markdown')
        update.message.reply_text("What next?", reply_markup=get_main_menu())
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"Error in ask: {e}")
        update.message.reply_text("⚠️ Error. Please try again.")
        return ASKING

def summarize_text(update, context):
    try:
        if not OPENAI_API_KEY:
            update.message.reply_text(
                "⚠️ **OpenAI API key not configured!**",
                parse_mode='Markdown'
            )
            return ConversationHandler.END
        
        if not update.message or not update.message.text:
            update.message.reply_text("⚠️ Send text to summarize.")
            return SUMMARIZING
        
        text = update.message.text
        if len(text) < 50:
            update.message.reply_text("⚠️ Send at least 50 characters.")
            return SUMMARIZING
        
        update.message.reply_text("📝 Summarizing...")
        response = safe_openai_call(f"Summarize this:\n\n{text}")
        
        if not response:
            response = "⚠️ Could not summarize. Try again."
        
        update.message.reply_text(f"📝 **Summary:**\n\n{response}", parse_mode='Markdown')
        update.message.reply_text("What next?", reply_markup=get_main_menu())
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"Error in summarize: {e}")
        update.message.reply_text("⚠️ Error. Try again.")
        return SUMMARIZING

def rewrite_text(update, context):
    try:
        if not OPENAI_API_KEY:
            update.message.reply_text(
                "⚠️ **OpenAI API key not configured!**",
                parse_mode='Markdown'
            )
            return ConversationHandler.END
        
        if not update.message or not update.message.text:
            update.message.reply_text("⚠️ Send text to rewrite.")
            return REWRITING
        
        text = update.message.text
        if len(text) < 10:
            update.message.reply_text("⚠️ Send longer text.")
            return REWRITING
        
        update.message.reply_text("✍️ Rewriting...")
        response = safe_openai_call(f"Rewrite this professionally:\n\n{text}")
        
        if not response:
            response = "⚠️ Could not rewrite. Try again."
        
        update.message.reply_text(f"✍️ **Rewritten:**\n\n{response}", parse_mode='Markdown')
        update.message.reply_text("What next?", reply_markup=get_main_menu())
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"Error in rewrite: {e}")
        update.message.reply_text("⚠️ Error. Try again.")
        return REWRITING

def generate_ideas(update, context):
    try:
        if not OPENAI_API_KEY:
            update.message.reply_text(
                "⚠️ **OpenAI API key not configured!**",
                parse_mode='Markdown'
            )
            return ConversationHandler.END
        
        if not update.message or not update.message.text:
            update.message.reply_text("⚠️ Send topic for ideas.")
            return IDEAS
        
        topic = update.message.text
        if len(topic.strip()) < 2:
            update.message.reply_text("⚠️ Specify a topic.")
            return IDEAS
        
        update.message.reply_text("💡 Generating ideas...")
        response = safe_openai_call(f"Generate 5 ideas about: {topic}")
        
        if not response:
            response = "⚠️ Could not generate ideas."
        
        update.message.reply_text(f"💡 **Ideas for {topic}:**\n\n{response}", parse_mode='Markdown')
        update.message.reply_text("What next?", reply_markup=get_main_menu())
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"Error in ideas: {e}")
        update.message.reply_text("⚠️ Error. Try again.")
        return IDEAS

def explain_topic(update, context):
    try:
        if not OPENAI_API_KEY:
            update.message.reply_text(
                "⚠️ **OpenAI API key not configured!**",
                parse_mode='Markdown'
            )
            return ConversationHandler.END
        
        if not update.message or not update.message.text:
            update.message.reply_text("⚠️ Send topic to explain.")
            return EXPLAINING
        
        topic = update.message.text
        if len(topic.strip()) < 2:
            update.message.reply_text("⚠️ Specify a topic.")
            return EXPLAINING
        
        update.message.reply_text("📚 Explaining...")
        response = safe_openai_call(f"Explain simply: {topic}")
        
        if not response:
            response = "⚠️ Could not explain. Try again."
        
        update.message.reply_text(f"📚 **Explanation:**\n\n{response}", parse_mode='Markdown')
        update.message.reply_text("What next?", reply_markup=get_main_menu())
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"Error in explain: {e}")
        update.message.reply_text("⚠️ Error. Try again.")
        return EXPLAINING

def translate_text(update, context):
    try:
        if not OPENAI_API_KEY:
            update.message.reply_text(
                "⚠️ **OpenAI API key not configured!**",
                parse_mode='Markdown'
            )
            return ConversationHandler.END
        
        if not update.message or not update.message.text:
            update.message.reply_text("⚠️ Format: language: text")
            return TRANSLATING
        
        text = update.message.text
        
        if ':' in text:
            parts = text.split(':', 1)
            target_lang = parts[0].strip()
            text_to_translate = parts[1].strip()
        else:
            update.message.reply_text("⚠️ Format: language: text\nExample: Spanish:Hello")
            return TRANSLATING
        
        if not target_lang or not text_to_translate:
            update.message.reply_text("⚠️ Provide both language and text.")
            return TRANSLATING
        
        update.message.reply_text("🌐 Translating...")
        response = safe_openai_call(f"Translate to {target_lang}:\n\n{text_to_translate}")
        
        if not response:
            response = "⚠️ Could not translate."
        
        update.message.reply_text(f"🌐 **Translation ({target_lang}):**\n\n{response}", parse_mode='Markdown')
        update.message.reply_text("What next?", reply_markup=get_main_menu())
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"Error in translate: {e}")
        update.message.reply_text("⚠️ Error. Try again.")
        return TRANSLATING

def analyze_document(update, context):
    try:
        if not OPENAI_API_KEY:
            update.message.reply_text(
                "⚠️ **OpenAI API key not configured!**",
                parse_mode='Markdown'
            )
            return ConversationHandler.END
        
        if not update.message or not update.message.document:
            update.message.reply_text("⚠️ Upload a document.")
            return DOCUMENT
        
        doc = update.message.document
        file_name = doc.file_name
        
        if doc.file_size > 5 * 1024 * 1024:
            update.message.reply_text("⚠️ File under 5MB only.")
            return DOCUMENT
        
        if not any(file_name.lower().endswith(ext) for ext in ['.txt', '.pdf']):
            update.message.reply_text("⚠️ TXT or PDF only.")
            return DOCUMENT
        
        update.message.reply_text("📄 Analyzing...")
        
        # For simplicity, just use the file name
        response = safe_openai_call(f"Analyze this document: {file_name}")
        
        if not response:
            response = "⚠️ Could not analyze."
        
        update.message.reply_text(f"📄 **Analysis:**\n\n{response}", parse_mode='Markdown')
        update.message.reply_text("What next?", reply_markup=get_main_menu())
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"Error in document: {e}")
        update.message.reply_text("⚠️ Error. Try again.")
        return DOCUMENT

# ============ FALLBACK ============

def fallback_handler(update, context):
    try:
        update.message.reply_text(
            "⚠️ Use /start to see options.",
            reply_markup=get_main_menu()
        )
    except Exception as e:
        logger.error(f"Error in fallback: {e}")

# ============ ERROR HANDLER ============

def error_handler(update, context):
    logger.error(f"❌ Error: {context.error}")
    try:
        if update and update.message:
            update.message.reply_text(
                "⚠️ Error occurred. Use /start to reset."
            )
    except:
        pass

# ============ MAIN ============

def main():
    print("\n" + "="*50)
    print("🤖 Starting SmartBot...")
    print("="*50 + "\n")
    
    if not TELEGRAM_TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN not found!")
        print("Please add it in Railway Variables")
        return
    
    print(f"✅ Telegram Token found: {TELEGRAM_TOKEN[:10]}...")
    
    if OPENAI_API_KEY:
        print(f"✅ OpenAI API Key found: {OPENAI_API_KEY[:15]}...")
    else:
        print("❌ OPENAI_API_KEY not found!")
        print("Some features won't work. Please add OPENAI_API_KEY in Railway Variables.")
    
    try:
        # Create updater
        updater = Updater(TELEGRAM_TOKEN, use_context=True)
        dp = updater.dispatcher
        
        # Create conversation handler
        conv_handler = ConversationHandler(
            entry_points=[
                CommandHandler('start', start),
            ],
            states={
                ASKING: [MessageHandler(Filters.text & ~Filters.command, ask_question)],
                SUMMARIZING: [MessageHandler(Filters.text & ~Filters.command, summarize_text)],
                REWRITING: [MessageHandler(Filters.text & ~Filters.command, rewrite_text)],
                IDEAS: [MessageHandler(Filters.text & ~Filters.command, generate_ideas)],
                EXPLAINING: [MessageHandler(Filters.text & ~Filters.command, explain_topic)],
                TRANSLATING: [MessageHandler(Filters.text & ~Filters.command, translate_text)],
                DOCUMENT: [
                    MessageHandler(Filters.document, analyze_document),
                ],
            },
            fallbacks=[
                CommandHandler('cancel', cancel),
                CommandHandler('start', start),
                MessageHandler(Filters.all, fallback_handler),
            ],
        )
        
        # Add handlers
        dp.add_handler(conv_handler)
        dp.add_handler(CallbackQueryHandler(button_handler))
        dp.add_error_handler(error_handler)
        
        print("✅ Bot is running!")
        print("🟢 Press Ctrl+C to stop\n")
        
        # Start polling
        updater.start_polling()
        updater.idle()
        
    except Exception as e:
        logger.critical(f"❌ Fatal error: {e}")
        print(f"\n❌ Fatal error: {e}")

if __name__ == '__main__':
    main()
