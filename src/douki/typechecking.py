"""
title: Runtime contracts for the documentation API.
"""

from typing import Callable, ParamSpec, TypeVar

from public import private
from typeguard import CollectionCheckStrategy, ForwardRefPolicy
from typeguard import typechecked as instrument

P = ParamSpec('P')
R = TypeVar('R')


@private
def typechecked(function: Callable[P, R]) -> Callable[P, R]:
    """
    title: Check every argument and collection item without wrapping calls.
    parameters:
      function:
        description: Annotated function to instrument for runtime type checks.
    returns: Instrumented function checking all arguments and collection items.
    """
    return instrument(
        collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        forward_ref_policy=ForwardRefPolicy.ERROR,
    )(function)
