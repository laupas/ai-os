from dependency_injector import containers, providers

from aios.agents.agent_catalog import AgentCatalog
from aios.agents.agent_grant_rule import AgentGrantRule
from aios.agents.skill_catalog import SkillCatalog


class AgentsContainer(containers.DeclarativeContainer):
    """Agents and skills, and the rule that holds each agent to its grants."""

    agents = providers.Dependency()
    skills = providers.Dependency()
    connectors = providers.Dependency()

    catalog = providers.Singleton(AgentCatalog, agents=agents)
    skill_catalog = providers.Singleton(SkillCatalog, skills=skills)
    grant_rule = providers.Singleton(AgentGrantRule, agents=catalog, connectors=connectors)
