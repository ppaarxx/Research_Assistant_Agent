from __future__ import annotations

from app.agents.compiler import compiler_node as compiler_agent_node
from app.agents.scraper import scraper_node as scraper_agent_node
from app.agents.summarizer import summarizer_node as summarizer_agent_node
from app.agents.supervisor import supervisor_node as supervisor_agent_node
from app.agents.web_search import web_search_node as web_search_agent_node


async def supervisor_node(state):
    return await supervisor_agent_node(state)


async def web_search_node(state):
    return await web_search_agent_node(state)


async def scraper_node(state):
    return await scraper_agent_node(state)


async def summarizer_node(state):
    return await summarizer_agent_node(state)


async def compiler_node(state):
    return await compiler_agent_node(state)
