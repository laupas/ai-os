from dependency_injector import containers, providers

from aios.variables.secret_box import SecretBox
from aios.variables.secret_extractor import SecretExtractor
from aios.variables.variable_catalog import VariableCatalog
from aios.variables.variable_resolver import VariableResolver


class VariablesContainer(containers.DeclarativeContainer):
    """Variables and secrets set in the console, filling them into connectors, and
    moving literal secrets out of connector configs."""

    variables = providers.Dependency()
    settings = providers.Dependency()
    clock = providers.Dependency()

    box = providers.Singleton(
        SecretBox,
        env_key=settings.provided.secrets_key,
        key_file=settings.provided.secrets_key_file.call(),
    )
    catalog = providers.Singleton(VariableCatalog, variables=variables, box=box, clock=clock)
    resolver = providers.Singleton(
        VariableResolver,
        variables=variables,
        box=box,
        files_dir=settings.provided.variable_files_dir.call(),
    )
    extractor = providers.Singleton(SecretExtractor, variables=catalog, resolver=resolver)
