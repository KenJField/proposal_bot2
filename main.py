"""Main entry point for the Proposal Automation System."""

import asyncio
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from database import db
from agents.email_triage import process_unread_emails
from agents.project_tracking import run_daily_tracking
from agents.knowledge import run_nightly_knowledge_extraction


async def initialize():
    """Initialize the system."""
    print("=" * 60)
    print("Proposal Automation System")
    print("=" * 60)

    # Initialize database connection
    await db.initialize()
    print("✓ System initialized")


async def run_email_processing():
    """Run email processing workflow."""
    print("\n--- Running Email Processing ---")
    try:
        result = await process_unread_emails(max_emails=10)
        print(f"✓ Email processing completed")
        print(f"Result: {result}")
    except Exception as e:
        print(f"✗ Error in email processing: {e}")


async def run_project_tracking():
    """Run daily project tracking."""
    print("\n--- Running Project Tracking ---")
    try:
        result = await run_daily_tracking()
        print(f"✓ Project tracking completed")
        print(f"Result: {result}")
    except Exception as e:
        print(f"✗ Error in project tracking: {e}")


async def run_knowledge_extraction():
    """Run nightly knowledge extraction."""
    print("\n--- Running Knowledge Extraction ---")
    try:
        result = await run_nightly_knowledge_extraction()
        print(f"✓ Knowledge extraction completed")
        print(f"Result: {result}")
    except Exception as e:
        print(f"✗ Error in knowledge extraction: {e}")


async def cleanup():
    """Cleanup resources."""
    await db.close()
    print("\n✓ System shutdown complete")


async def main():
    """Main application loop."""
    try:
        await initialize()

        # For demonstration, run one cycle of each workflow
        # In production, these would be scheduled via cron or LangSmith Deployment

        print("\n" + "=" * 60)
        print("Running Workflows")
        print("=" * 60)

        # 1. Process emails (would run every 2 minutes via polling/webhook)
        await run_email_processing()

        # 2. Track projects (would run daily at 9 AM via cron)
        # await run_project_tracking()

        # 3. Extract knowledge (would run nightly at 2 AM via cron)
        # await run_knowledge_extraction()

    except KeyboardInterrupt:
        print("\n\n✗ Interrupted by user")
    except Exception as e:
        print(f"\n✗ Fatal error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await cleanup()


if __name__ == "__main__":
    print("""
    ╔══════════════════════════════════════════════════════════════╗
    ║                                                              ║
    ║           Proposal Automation System                         ║
    ║           Multi-Agent AI for Market Research RFPs            ║
    ║                                                              ║
    ╚══════════════════════════════════════════════════════════════╝
    """)

    asyncio.run(main())
