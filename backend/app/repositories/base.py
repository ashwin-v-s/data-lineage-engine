"""Abstract repository interfaces for Kairos lineage, entity, and evidence data access.

M5 code relies strictly on these interfaces so switching from mock data to real
PostgreSQL/M3 storage happens at the repository layer without changing API or UI code.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple


class BaseEntityRepository(ABC):
    @abstractmethod
    def get_by_id(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve entity by canonical ID."""
        pass

    @abstractmethod
    def get_by_fqn(self, fqn: str) -> Optional[Dict[str, Any]]:
        """Retrieve entity by fully qualified name."""
        pass

    @abstractmethod
    def search(self, query: str, entity_type: Optional[str] = None, limit: int = 20) -> Tuple[List[Dict[str, Any]], int]:
        """Search entities by text match."""
        pass


class BaseLineageRepository(ABC):
    @abstractmethod
    def get_graph(
        self,
        entity_id: str,
        granularity: str = "COLUMN",
        depth: int = 3,
        valid_at: Optional[str] = None,
        known_as_of: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Retrieve lineage graph centered at entity_id under half-open bitemporal slicing."""
        pass

    @abstractmethod
    def get_upstream(
        self,
        entity_id: str,
        depth: int = 1,
        valid_at: Optional[str] = None,
        known_as_of: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Retrieve upstream lineage only."""
        pass

    @abstractmethod
    def get_downstream(
        self,
        entity_id: str,
        depth: int = 1,
        valid_at: Optional[str] = None,
        known_as_of: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Retrieve downstream lineage only."""
        pass


class BaseEvidenceRepository(ABC):
    @abstractmethod
    def get_evidence_by_id(self, evidence_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve complete evidence dossier by evidence_id."""
        pass

    @abstractmethod
    def get_by_entity(
        self,
        entity_id: str,
        evidence_type: Optional[str] = None,
        source_system: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Retrieve evidence list for an entity."""
        pass

    @abstractmethod
    def search_evidence(
        self,
        evidence_type: Optional[str] = None,
        source_system: Optional[str] = None,
        granularity: Optional[str] = None,
        operator: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Search evidence records with multi-attribute filtering."""
        pass
