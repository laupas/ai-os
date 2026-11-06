from dependency_injector import containers, providers

from aios.agents.repo_agent_reader import RepoAgentReader
from aios.agents.repo_skill_reader import RepoSkillReader
from aios.config_repo.config_branches import ConfigBranches
from aios.config_repo.config_remote import ConfigRemote
from aios.config_repo.config_repo_initializer import ConfigRepoInitializer
from aios.config_repo.config_repo_watcher import ConfigRepoWatcher
from aios.config_repo.remote_from_environment import RemoteFromEnvironment
from aios.config_repo.repository_file_check import RepositoryFileCheck
from aios.config_repo.repository_files import RepositoryFiles
from aios.config_repo.skills_link import SkillsLink


class ConfigRepoContainer(containers.DeclarativeContainer):
    """The configuration repository's first start, its link for the CLI's skills,
    and the watcher that picks up commits made outside ai-os."""

    repo_dir = providers.Dependency()
    store = providers.Dependency()
    legacy_store = providers.Dependency()
    collections = providers.Dependency()
    mcp_servers = providers.Dependency(default={})
    remotes = providers.Dependency()
    box = providers.Dependency()
    clock = providers.Dependency()
    known_hosts = providers.Dependency()
    settings = providers.Dependency()

    initializer = providers.Singleton(
        ConfigRepoInitializer,
        store=store,
        legacy=legacy_store,
        collections=collections,
        agent_reader=providers.Singleton(
            RepoAgentReader, agents_dir=providers.Callable(lambda r: r / "agents", repo_dir)
        ),
        skill_reader=providers.Singleton(
            RepoSkillReader, skills_dir=providers.Callable(lambda r: r / "skills", repo_dir)
        ),
        mcp_servers=mcp_servers,
        legacy_config=settings.provided.legacy_config_file.call(),
    )
    skills_link = providers.Singleton(
        SkillsLink,
        link=providers.Callable(lambda r: r / ".claude" / "skills", repo_dir),
        target=providers.Callable(lambda s: s.repo.root / "skills", store),
    )
    watcher = providers.Singleton(ConfigRepoWatcher, store=store, collections=collections)
    files = providers.Singleton(
        RepositoryFiles,
        store=store,
        watcher=watcher,
        check=providers.Singleton(RepositoryFileCheck, store=store, collections=collections),
    )
    branches = providers.Singleton(ConfigBranches, store=store, collections=collections)
    remote = providers.Singleton(
        ConfigRemote,
        store=store,
        remotes=remotes,
        box=box,
        clock=clock,
        known_hosts=known_hosts,
        collections=collections,
    )
    remote_from_env = providers.Singleton(
        RemoteFromEnvironment,
        remote=remote,
        url=settings.provided.config_remote,
        ssh_key=settings.provided.config_ssh_key,
        token=settings.provided.config_token,
    )
