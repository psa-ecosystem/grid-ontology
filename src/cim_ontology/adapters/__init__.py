"""Stage 3: 输出适配器。"""
from cim_ontology.adapters.base import ADAPTERS, EmitResult, OutputAdapter, VerifyResult, get_adapter
from cim_ontology.adapters.owl import OwlTurtleAdapter
from cim_ontology.adapters.shacl import ShaclAdapter
from cim_ontology.adapters.jsonld_context import JsonLdContextAdapter
from cim_ontology.adapters.json_schema import JsonSchemaAdapter
from cim_ontology.adapters.python_types import PythonTypesAdapter

ADAPTERS["owl"] = OwlTurtleAdapter
ADAPTERS["shacl"] = ShaclAdapter
ADAPTERS["jsonld-context"] = JsonLdContextAdapter
ADAPTERS["json-schema"] = JsonSchemaAdapter
ADAPTERS["python-types"] = PythonTypesAdapter

__all__ = ["ADAPTERS", "EmitResult", "OutputAdapter", "VerifyResult", "get_adapter"]
