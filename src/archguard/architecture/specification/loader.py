import math
from typing import Annotated, cast

import yaml
from pydantic import Field, JsonValue, ValidationError
from yaml.events import AliasEvent, CollectionEndEvent, CollectionStartEvent, Event, ScalarEvent
from yaml.nodes import MappingNode, Node, ScalarNode, SequenceNode

from archguard.architecture.specification.errors import (
    ArchitectureSpecificationError,
    ArchitectureSpecResourceLimitError,
    UnsupportedArchitectureRuleError,
    UnsupportedArchitectureSpecVersionError,
)
from archguard.architecture.specification.models import ArchitectureSpecification, RuleType
from archguard.core.model.base import DomainModel


class ArchitectureSpecLoaderConfig(DomainModel):
    max_bytes: Annotated[int, Field(gt=0)] = 131_072
    max_depth: Annotated[int, Field(gt=0)] = 32
    max_nodes: Annotated[int, Field(gt=0)] = 10_000


def _value(node: Node) -> JsonValue:
    if isinstance(node, ScalarNode):
        tag = node.tag.removeprefix("tag:yaml.org,2002:")
        if tag == "str":
            return cast(str, node.value)
        if tag == "null":
            return None
        if tag == "bool":
            return cast(str, node.value).lower() in {"true", "yes", "on"}
        if tag == "int":
            try:
                return int(node.value.replace("_", ""), 10)
            except ValueError:
                raise ArchitectureSpecificationError(
                    "only decimal numeric scalars are supported"
                ) from None
        if tag == "float":
            try:
                value = float(node.value.replace("_", ""))
            except ValueError:
                raise ArchitectureSpecificationError("invalid numeric scalar") from None
            if math.isfinite(value):
                return value
        raise ArchitectureSpecificationError("unsupported YAML scalar/tag")
    if isinstance(node, SequenceNode):
        if node.tag != "tag:yaml.org,2002:seq":
            raise ArchitectureSpecificationError("invalid YAML sequence tag")
        return [_value(item) for item in node.value]
    if isinstance(node, MappingNode):
        if node.tag != "tag:yaml.org,2002:map":
            raise ArchitectureSpecificationError("invalid YAML mapping tag")
        result: dict[str, JsonValue] = {}
        for key, value in node.value:
            if not isinstance(key, ScalarNode) or key.tag != "tag:yaml.org,2002:str":
                raise ArchitectureSpecificationError(
                    "mapping keys must be strings; merge keys are forbidden"
                )
            if key.value in result:
                raise ArchitectureSpecificationError("duplicate YAML mapping key")
            result[key.value] = _value(value)
        return result
    raise ArchitectureSpecificationError("unsupported YAML node/tag")


class ArchitectureSpecLoader:
    def __init__(self, config: ArchitectureSpecLoaderConfig | None = None) -> None:
        self.config = config if config is not None else ArchitectureSpecLoaderConfig()

    def load(self, source: str | bytes) -> ArchitectureSpecification:
        if isinstance(source, str):
            try:
                data = source.encode("utf-8")
            except UnicodeError:
                raise ArchitectureSpecificationError("spec must be valid UTF-8") from None
        else:
            data = source
        if len(data) > self.config.max_bytes:
            raise ArchitectureSpecResourceLimitError("spec exceeds configured byte limit")
        try:
            text = data.decode("utf-8")
        except UnicodeError:
            raise ArchitectureSpecificationError("spec must be valid UTF-8") from None
        try:
            depth = 0
            count = 0
            for event in yaml.parse(text, Loader=yaml.SafeLoader):
                self._reject_alias(event)
                if isinstance(event, CollectionStartEvent):
                    depth += 1
                elif isinstance(event, CollectionEndEvent):
                    depth -= 1
                if isinstance(event, (CollectionStartEvent, ScalarEvent)):
                    count += 1
                if depth > self.config.max_depth or count > self.config.max_nodes:
                    raise ArchitectureSpecResourceLimitError(
                        "spec exceeds configured structure limit"
                    )
            node = yaml.compose(text, Loader=yaml.SafeLoader)
            if node is None:
                raise ArchitectureSpecificationError("spec cannot be empty")
            value = _value(node)
        except yaml.YAMLError as error:
            mark = getattr(error, "problem_mark", None)
            raise ArchitectureSpecificationError(
                "invalid YAML",
                line=mark.line + 1 if mark else None,
                column=mark.column + 1 if mark else None,
            ) from None
        if not isinstance(value, dict):
            raise ArchitectureSpecificationError("spec root must be a mapping")
        if "version" in value and value["version"] != "1.0":
            raise UnsupportedArchitectureSpecVersionError(
                "only architecture specification version 1.0 is supported"
            )
        rules = value.get("rules", [])
        if isinstance(rules, list):
            for rule in rules:
                if isinstance(rule, dict) and rule.get("type") not in {
                    item.value for item in RuleType
                }:
                    raise UnsupportedArchitectureRuleError(
                        "rule type is unsupported in specification v1"
                    )
        try:
            return ArchitectureSpecification.model_validate(value, by_alias=True, by_name=False)
        except ValidationError:
            raise ArchitectureSpecificationError(
                "architecture specification schema or references are invalid"
            ) from None

    @staticmethod
    def _reject_alias(event: Event) -> None:
        if isinstance(event, AliasEvent) or getattr(event, "anchor", None) is not None:
            raise ArchitectureSpecificationError("YAML aliases and anchors are forbidden in v1")
        tag = cast(str | None, getattr(event, "tag", None))
        if tag is not None and tag not in {
            "tag:yaml.org,2002:" + name
            for name in ("str", "null", "bool", "int", "float", "seq", "map")
        }:
            raise ArchitectureSpecificationError(
                "custom YAML tags and object constructors are forbidden"
            )
