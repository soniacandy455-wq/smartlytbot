import os
import logging
import asyncio
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler
)
import openai

# Load environment variables - Try multiple ways
load_dotenv()

# Try to get API key from environment
openai_api_key = os.getenv('OPENAI_API_KEY')

# If not found, try reading from .env file directly
if not openai_api_key:
    try:
        with open('.env', 'r') as f:
            for line in f:
                if line.startswith('OPENAI_API_KEY='):
                    openai_api_key = line.split('=')[1].strip()
                    break
    except:
        pass

# Set OpenAI API key
if openai_api_key:
    openai.api_key = openai_api_key
    print("✅ OpenAI API key loaded successfully")
else:
    print("❌ OPENAI_API_KEY not found! Some features won't work.")

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

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

# ============ SAFE OPENAI CALL WITH RETRY ============

async def safe_openai_call(prompt: str, max_retries: int = 3) -> str:
    """Safely call OpenAI with retry logic"""
    if not openai_api_key:
        return "⚠️ OpenAI API key not configured. Please set OPENAI_API_KEY in Railway variables."
    
    for attempt in range(max_retries):
        try:
            client = openai.OpenAI(api_key=openai_api_key)
            response = await asyncio.to_thread(
                client.chat.completions.create,
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=500,
                temperature=0.7,
                timeout=30
            )
            
            if response and response.choices:
                return response.choices[0].message.content
            else:
                raise Exception("Empty response")
                
        except openai.APIConnectionError:
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)
                continue
            return "🔌 Connection issue. Please try again."
            
        except openai.RateLimitError:
            if attempt < max_retries - 1:
                await asyncio.sleep(5 * (attempt + 1))
                continue
            return "⏰ Rate limit exceeded. Please wait."
            
        except Exception as e:
            logger.error(f"OpenAI error: {e}")
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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data.clear()
        
        # Check if API key is configured
        if not openai_api_key:
            warning = "⚠️ **Notice:** OpenAI API key not configured.\n\n"
        else:
            warning = ""
        
        welcome = (
            "🤖 **Welcome to SmartBot!**\n\n"
            f"{warning}"
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
        await update.message.reply_text(welcome, reply_markup=get_main_menu(), parse_mode='Markdown')
        return ConversationHandler.END
    except Exception as e:
        logger.error(f"Error in start: {e}")
        await update.message.reply_text("⚠️ Please try /start again.")
        return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data.clear()
        await update.message.reply_text(
            "✅ Cancelled. Use /start to see options.",
            reply_markup=get_main_menu()
        )
        return ConversationHandler.END
    except Exception as e:
        logger.error(f"Error in cancel: {e}")
        return ConversationHandler.END

# ============ BUTTON HANDLER ============

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        await query.answer()
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
        await query.edit_message_text(message, reply_markup=None)
        
        if state is not None:
            context.user_data['action'] = action
            return state
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"Error in button: {e}")
        await query.edit_message_text("⚠️ Error. Use /start to try again.")
        return ConversationHandler.END

# ============ FEATURE HANDLERS ============

async def ask_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not openai_api_key:
            await update.message.reply_text(
                "⚠️ **OpenAI API key not configured!**\n\n"
                "Please add OPENAI_API_KEY in Railway variables.\n"
                "Contact the bot administrator.",
                parse_mode='Markdown'
            )
            return ConversationHandler.END
        
        if not update.message or not update.message.text:
            await update.message.reply_text("⚠️ Please send your question.")
            return ASKING
        
        question = update.message.text
        if len(question.strip()) < 2:
            await update.message.reply_text("⚠️ Please ask a longer question.")
            return ASKING
        
        msg = await update.message.reply_text("🤔 Thinking...")
        response = await safe_openai_call(f"Answer this: {question}")
        
        if not response:
            response = "⚠️ Could not generate response. Please try again."
        
        try:
            await msg.edit_text(f"💬 **Answer:**\n\n{response}", parse_mode='Markdown')
        except:
            await update.message.reply_text(f"💬 **Answer:**\n\n{response}", parse_mode='Markdown')
        
        await update.message.reply_text("What next?", reply_markup=get_main_menu())
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"Error in ask: {e}")
        await update.message.reply_text("⚠️ Error. Please try again.")
        return ASKING

async def summarize_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not openai_api_key:
            await update.message.reply_text(
                "⚠️ **OpenAI API key not configured!**\n\n"
                "Please add OPENAI_API_KEY in Railway variables.",
                parse_mode='Markdown'
            )
            return ConversationHandler.END
        
        if not update.message or not update.message.text:
            await update.message.reply_text("⚠️ Send text to summarize.")
            return SUMMARIZING
        
        text = update.message.text
        if len(text) < 50:
            await update.message.reply_text("⚠️ Send at least 50 characters.")
            return SUMMARIZING
        
        msg = await update.message.reply_text("📝 Summarizing...")
        response = await safe_openai_call(f"Summarize this:\n\n{text}")
        
        if not response:
            response = "⚠️ Could not summarize. Try again."
        
        try:
            await msg.edit_text(f"📝 **Summary:**\n\n{response}", parse_mode='Markdown')
        except:
            await update.message.reply_text(f"📝 **Summary:**\n\n{response}", parse_mode='Markdown')
        
        await update.message.reply_text("What next?", reply_markup=get_main_menu())
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"Error in summarize: {e}")
        await update.message.reply_text("⚠️ Error. Try again.")
        return SUMMARIZING

async def rewrite_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not openai_api_key:
            await update.message.reply_text(
                "⚠️ **OpenAI API key not configured!**\n\n"
                "Please add OPENAI_API_KEY in Railway variables.",
                parse_mode='Markdown'
            )
            return ConversationHandler.END
        
        if not update.message or not update.message.text:
            await update.message.reply_text("⚠️ Send text to rewrite.")
            return REWRITING
        
        text = update.message.text
        if len(text) < 10:
            await update.message.reply_text("⚠️ Send longer text.")
            return REWRITING
        
        msg = await update.message.reply_text("✍️ Rewriting...")
        response = await safe_openai_call(f"Rewrite this professionally:\n\n{text}")
        
        if not response:
            response = "⚠️ Could not rewrite. Try again."
        
        try:
            await msg.edit_text(f"✍️ **Rewritten:**\n\n{response}", parse_mode='Markdown')
        except:
            await update.message.reply_text(f"✍️ **Rewritten:**\n\n{response}", parse_mode='Markdown')
        
        await update.message.reply_text("What next?", reply_markup=get_main_menu())
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"Error in rewrite: {e}")
        await update.message.reply_text("⚠️ Error. Try again.")
        return REWRITING

async def generate_ideas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not openai_api_key:
            await update.message.reply_text(
                "⚠️ **OpenAI API key not configured!**\n\n"
                "Please add OPENAI_API_KEY in Railway variables.",
                parse_mode='Markdown'
            )
            return ConversationHandler.END
        
        if not update.message or not update.message.text:
            await update.message.reply_text("⚠️ Send topic for ideas.")
            return IDEAS
        
        topic = update.message.text
        if len(topic.strip()) < 2:
            await update.message.reply_text("⚠️ Specify a topic.")
            return IDEAS
        
        msg = await update.message.reply_text("💡 Generating ideas...")
        response = await safe_openai_call(f"Generate 5 ideas about: {topic}")
        
        if not response:
            response = "⚠️ Could not generate ideas."
        
        try:
            await msg.edit_text(f"💡 **Ideas for {topic}:**\n\n{response}", parse_mode='Markdown')
        except:
            await update.message.reply_text(f"💡 **Ideas for {topic}:**\n\n{response}", parse_mode='Markdown')
        
        await update.message.reply_text("What next?", reply_markup=get_main_menu())
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"Error in ideas: {e}")
        await update.message.reply_text("⚠️ Error. Try again.")
        return IDEAS

async def explain_topic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not openai_api_key:
            await update.message.reply_text(
                "⚠️ **OpenAI API key not configured!**\n\n"
                "Please add OPENAI_API_KEY in Railway variables.",
                parse_mode='Markdown'
            )
            return ConversationHandler.END
        
        if not update.message or not update.message.text:
            await update.message.reply_text("⚠️ Send topic to explain.")
            return EXPLAINING
        
        topic = update.message.text
        if len(topic.strip()) < 2:
            await update.message.reply_text("⚠️ Specify a topic.")
            return EXPLAINING
        
        msg = await update.message.reply_text("📚 Explaining...")
        response = await safe_openai_call(f"Explain simply: {topic}")
        
        if not response:
            response = "⚠️ Could not explain. Try again."
        
        try:
            await msg.edit_text(f"📚 **Explanation:**\n\n{response}", parse_mode='Markdown')
        except:
            await update.message.reply_text(f"📚 **Explanation:**\n\n{response}", parse_mode='Markdown')
        
        await update.message.reply_text("What next?", reply_markup=get_main_menu())
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"Error in explain: {e}")
        await update.message.reply_text("⚠️ Error. Try again.")
        return EXPLAINING

async def translate_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not openai_api_key:
            await update.message.reply_text(
                "⚠️ **OpenAI API key not configured!**\n\n"
                "Please add OPENAI_API_KEY in Railway variables.",
                parse_mode='Markdown'
            )
            return ConversationHandler.END
        
        if not update.message or not update.message.text:
            await update.message.reply_text("⚠️ Format: language: text")
            return TRANSLATING
        
        text = update.message.text
        
        if ':' in text:
            parts = text.split(':', 1)
            target_lang = parts[0].strip()
            text_to_translate = parts[1].strip()
        else:
            await update.message.reply_text("⚠️ Format: language: text\nExample: Spanish:Hello")
            return TRANSLATING
        
        if not target_lang or not text_to_translate:
            await update.message.reply_text("⚠️ Provide both language and text.")
            return TRANSLATING
        
        msg = await update.message.reply_text("🌐 Translating...")
        response = await safe_openai_call(f"Translate to {target_lang}:\n\n{text_to_translate}")
        
        if not response:
            response = "⚠️ Could not translate."
        
        try:
            await msg.edit_text(f"🌐 **Translation ({target_lang}):**\n\n{response}", parse_mode='Markdown')
        except:
            await update.message.reply_text(f"🌐 **Translation ({target_lang}):**\n\n{response}", parse_mode='Markdown')
        
        await update.message.reply_text("What next?", reply_markup=get_main_menu())
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"Error in translate: {e}")
        await update.message.reply_text("⚠️ Error. Try again.")
        return TRANSLATING

async def analyze_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not openai_api_key:
            await update.message.reply_text(
                "⚠️ **OpenAI API key not configured!**\n\n"
                "Please add OPENAI_API_KEY in Railway variables.",
                parse_mode='Markdown'
            )
            return ConversationHandler.END
        
        if not update.message or not update.message.document:
            await update.message.reply_text("⚠️ Upload a document.")
            return DOCUMENT
        
        doc = update.message.document
        file_name = doc.file_name
        
        if doc.file_size > 5 * 1024 * 1024:
            await update.message.reply_text("⚠️ File under 5MB only.")
            return DOCUMENT
        
        if not any(file_name.lower().endswith(ext) for ext in ['.txt', '.pdf']):
            await update.message.reply_text("⚠️ TXT or PDF only.")
            return DOCUMENT
        
        msg = await update.message.reply_text("📄 Analyzing...")
        
        file = await doc.get_file()
        file_content = await file.download_as_bytearray()
        
        if file_name.lower().endswith('.txt'):
            text = file_content.decode('utf-8', errors='ignore')
        else:
            text = "PDF content preview: " + str(file_content[:500])
        
        response = await safe_openai_call(f"Summarize this document:\n\n{text[:2000]}")
        
        if not response:
            response = "⚠️ Could not analyze."
        
        try:
            await msg.edit_text(f"📄 **Analysis:**\n\n{response}", parse_mode='Markdown')
        except:
            await update.message.reply_text(f"📄 **Analysis:**\n\n{response}", parse_mode='Markdown')
        
        await update.message.reply_text("What next?", reply_markup=get_main_menu())
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"Error in document: {e}")
        await update.message.reply_text("⚠️ Error. Try again.")
        return DOCUMENT

# ============ FALLBACK ============

async def fallback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await update.message.reply_text(
            "⚠️ Use /start to see options.",
            reply_markup=get_main_menu()
        )
    except Exception as e:
        logger.error(f"Error in fallback: {e}")

# ============ ERROR HANDLER ============

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"❌ Error: {context.error}")
    try:
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "⚠️ Error occurred. Use /start to reset."
            )
    except:
        pass

# ============ MAIN ============

def main():
    print("\n" + "="*50)
    print("🤖 Starting SmartBot...")
    print("="*50 + "\n")
    
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    
    if not bot_token:
        print("❌ TELEGRAM_BOT_TOKEN not found!")
        print("Please add it in Railway Variables")
        return
    
    print(f"✅ Telegram Token found: {bot_token[:10]}...")
    
    if openai_api_key:
        print(f"✅ OpenAI API Key found: {openai_api_key[:10]}...")
    else:
        print("❌ OPENAI_API_KEY not found!")
        print("Some features won't work. Please add OPENAI_API_KEY in Railway Variables.")
    
    try:
        app = Application.builder().token(bot_token).build()
        
        conv_handler = ConversationHandler(
            entry_points=[
                CommandHandler('start', start),
            ],
            states={
                ASKING: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_question)],
                SUMMARIZING: [MessageHandler(filters.TEXT & ~filters.COMMAND, summarize_text)],
                REWRITING: [MessageHandler(filters.TEXT & ~filters.COMMAND, rewrite_text)],
                IDEAS: [MessageHandler(filters.TEXT & ~filters.COMMAND, generate_ideas)],
                EXPLAINING: [MessageHandler(filters.TEXT & ~filters.COMMAND, explain_topic)],
                TRANSLATING: [MessageHandler(filters.TEXT & ~filters.COMMAND, translate_text)],
                DOCUMENT: [
                    MessageHandler(filters.Document.ALL, analyze_document),
                ],
            },
            fallbacks=[
                CommandHandler('cancel', cancel),
                CommandHandler('start', start),
                MessageHandler(filters.ALL, fallback_handler),
            ],
        )
        
        app.add_handler(conv_handler)
        app.add_handler(CallbackQueryHandler(button_handler))
        app.add_error_handler(error_handler)
        
        print("✅ Bot is running!")
        print("🟢 Press Ctrl+C to stop\n")
        
        app.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True
        )
        
    except Exception as e:
        logger.critical(f"❌ Fatal error: {e}")
        print(f"\n❌ Fatal error: {e}")

if __name__ == '__main__':
    main()
