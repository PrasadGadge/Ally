import asyncio
import edge_tts

# 1. Define your AI Assistant's voice configuration
VOICE = "en-US-AriaNeural"

SPEED = "+3%"
PITCH = "-7Hz" 

# 2. Define the response script
TEXT_TO_SPEAK = (
    "System online, sir. All core protocols have been loaded successfully. "
    "I am fully operational, highly accurate, and standing by for your direct commands."
)

OUTPUT_FILE = "aria_assistant.mp3"

async def generate_assistant_voice() -> None:
    """Generates the tuned Aria TTS audio file."""
    print(f"🔄 Calibrating {VOICE}...")
    
    # Initialize the edge-tts communicate object with the custom rate and pitch
    communicate = edge_tts.Communicate(
        text=TEXT_TO_SPEAK, 
        voice=VOICE, 
        rate=SPEED, 
        pitch=PITCH
    )
    
    # Save the file to disk
    await communicate.save(OUTPUT_FILE)
    print(f"✅ Audio successfully saved to: '{OUTPUT_FILE}'")

if __name__ == "__main__":
    # Run the asynchronous loop
    asyncio.run(generate_assistant_voice())
