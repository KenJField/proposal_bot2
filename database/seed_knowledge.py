"""Seed script for populating initial knowledge base."""

import asyncio
from dotenv import load_dotenv

load_dotenv()

from tools.knowledge import add_knowledge


async def seed_knowledge_base():
    """Populate knowledge base with initial data."""

    print("Seeding knowledge base...")

    # Capabilities
    capabilities = [
        {
            "content": "We offer comprehensive quantitative research services including online surveys, telephone interviews, and face-to-face interviews with sample sizes ranging from n=100 to n=10,000+",
            "type": "capability",
            "metadata": {"service": "quantitative", "methodologies": ["online_survey", "CATI", "CAPI"]}
        },
        {
            "content": "Expert qualitative research capabilities including in-depth interviews (IDIs), focus groups, ethnography, and online communities with experienced moderators",
            "type": "capability",
            "metadata": {"service": "qualitative", "methodologies": ["IDI", "focus_groups", "ethnography"]}
        },
        {
            "content": "Advanced analytics including conjoint analysis, MaxDiff, segmentation, and predictive modeling using R and Python",
            "type": "capability",
            "metadata": {"service": "analytics", "methodologies": ["conjoint", "maxdiff", "segmentation"]}
        }
    ]

    for cap in capabilities:
        result = await add_knowledge(cap["content"], cap["type"], cap["metadata"])
        print(f"✓ Added capability: {result}")

    # Team members
    team_members = [
        {
            "content": "Jane Smith - Senior Research Director with 15 years experience in brand tracking and segmentation studies. Expert in conjoint analysis and R programming. Rate: $175/hour",
            "type": "team_member",
            "metadata": {"name": "Jane Smith", "email": "jane@company.com", "skills": ["conjoint", "segmentation", "R"], "rate": 175}
        },
        {
            "content": "Bob Johnson - Programming Lead specializing in MaxDiff, Choice-Based Conjoint, and complex survey programming. Rate: $150/hour",
            "type": "team_member",
            "metadata": {"name": "Bob Johnson", "email": "bob@company.com", "skills": ["programming", "maxdiff", "CBC"], "rate": 150}
        }
    ]

    for member in team_members:
        result = await add_knowledge(member["content"], member["type"], member["metadata"])
        print(f"✓ Added team member: {result}")

    # Suppliers
    suppliers = [
        {
            "content": "Panel Provider Inc - Reliable US consumer panel with quick turnaround. Typical CPI: $8.50 for 10-minute survey",
            "type": "supplier",
            "metadata": {"supplier_name": "Panel Provider Inc", "email": "supplier@panel.com", "services": ["panel"], "typical_cpi": 8.5, "countries": ["US"]}
        },
        {
            "content": "Global Research Partners - International panel provider covering 50+ countries. Specialty in B2B and hard-to-reach audiences",
            "type": "supplier",
            "metadata": {"supplier_name": "Global Research Partners", "services": ["panel", "B2B"], "countries": ["global"]}
        }
    ]

    for supplier in suppliers:
        result = await add_knowledge(supplier["content"], supplier["type"], supplier["metadata"])
        print(f"✓ Added supplier: {result}")

    # Pricing guidelines
    pricing = [
        {
            "content": "Standard programming rate: $150/hour. Complex programming (conjoint, MaxDiff): $175/hour",
            "type": "pricing",
            "metadata": {"service": "programming", "base_rate": 150, "complex_rate": 175}
        },
        {
            "content": "Project management: 15% of total project cost. Rush projects (< 2 weeks): add 20% premium",
            "type": "pricing",
            "metadata": {"service": "project_management", "percentage": 15, "rush_premium": 20}
        }
    ]

    for price in pricing:
        result = await add_knowledge(price["content"], price["type"], price["metadata"])
        print(f"✓ Added pricing: {result}")

    print("\n✓ Knowledge base seeding complete!")


if __name__ == "__main__":
    asyncio.run(seed_knowledge_base())
