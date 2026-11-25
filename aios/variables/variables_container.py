from dependency_injector import containers, providers

from aios.variables.legacy_variable_files_removal import LegacyVariableFilesRemoval
from aios.variables.secret_box import SecretBox
from aios.variables.secret_extractor import SecretExtractor
from aios.variables.secrets_key_rotation import SecretsKeyRotation
from aios.variables.secrets_key_source import SecretsKeySource
from aios.variables.variable_catalog import VariableCatalog
from aios.variables.variable_resolver import VariableResolver


class VariablesContainer(containers.DeclarativeContainer):
    """Variables and secrets set in the console, filling them into connectors, and
    moving literal secrets out of connector configs. The secrets key and moving every
    stored secret onto a new one."""

    variables = providers.Dependency()
    settings = providers.Dependency()
    clock = providers.Dependency()
    encrypted = providers.Dependency()
    """`EncryptedFields` of every collection that stores secrets."""
    audit_trail = providers.Dependency()

    key_source = providers.Singleton(
        SecretsKeySource,
        setting=settings.provided.secrets_key,
        previous=settings.provided.secrets_key_previous,
        legacy_file=settings.provided.secrets_key_file.call(),
    )
    box = providers.Singleton(
        SecretBox,
        key=key_source.provided.current.call(),
        previous=key_source.provided.previous.call(),
    )
    rotation = providers.Singleton(
        SecretsKeyRotation,
        box=box,
        source=key_source,
        holders=encrypted,
        trail=audit_trail,
    )
    files_dir = providers.Callable(lambda s: s.variable_files_dir(), settings)
    legacy_files_removal = providers.Singleton(
        LegacyVariableFilesRemoval,
        legacy_dir=settings.provided.legacy_variable_files_dir.call(),
        files_dir=files_dir,
    )
    catalog = providers.Singleton(VariableCatalog, variables=variables, box=box, clock=clock)
    resolver = providers.Singleton(
        VariableResolver,
        variables=variables,
        box=box,
        files_dir=files_dir,
    )
    extractor = providers.Singleton(SecretExtractor, variables=catalog, resolver=resolver)
