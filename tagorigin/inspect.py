"""tagorigin inspect.py: pikepdf wrapper for metadata and structure extraction.

Opens a PDF with pikepdf and extracts the data needed by the signal modules.
No scoring logic here: just safe extraction and normalisation.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pikepdf
from lxml import etree


class PdfInspector:
    """Wraps an open pikepdf.Pdf and exposes the raw structures signals need."""

    def __init__(self, pdf: pikepdf.Pdf, path: Path | None = None) -> None:
        self.pdf = pdf
        self.path = path
        self.root = pdf.Root
        self.info = pdf.docinfo if hasattr(pdf, "docinfo") else {}
        self.xmp_xml: etree._Element | None = self._load_xmp()

        # Lazy caches
        self._tag_tally: dict[str, int] | None = None
        self._figures_with_alt: list[dict[str, Any]] | None = None
        self._tables_with_th: list[dict[str, Any]] | None = None
        self._actual_text_issues: list[dict[str, Any]] | None = None

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------
    @classmethod
    def open(cls, path: Path) -> PdfInspector:
        pdf = pikepdf.open(str(path))
        return cls(pdf, path)

    # ------------------------------------------------------------------
    # Basic file metadata
    # ------------------------------------------------------------------
    def file_size_bytes(self) -> int:
        if self.path:
            return self.path.stat().st_size
        return 0

    def file_md5(self) -> str:
        if not self.path:
            return ""
        h = hashlib.md5()  # noqa: S324
        h.update(self.path.read_bytes())
        return h.hexdigest()

    # ------------------------------------------------------------------
    # Low-level helpers
    # ------------------------------------------------------------------
    def _get(self, obj: Any, key: str) -> Any:
        if obj is None:
            return None
        try:
            return obj.get(key)
        except (AttributeError, KeyError, TypeError):
            return None

    def _bool(self, obj: Any, key: str) -> bool | None:
        val = self._get(obj, key)
        if val is None:
            return None
        if isinstance(val, bool):
            return val
        if isinstance(val, (int, float)):
            return bool(val)
        return None

    def _text(self, obj: Any) -> str:
        if obj is None:
            return ""
        if isinstance(obj, pikepdf.String):
            return str(obj)
        if isinstance(obj, bytes):
            return obj.decode("utf-8", errors="replace")
        return str(obj)

    # ------------------------------------------------------------------
    # XMP loading
    # ------------------------------------------------------------------
    def _load_xmp(self) -> etree._Element | None:
        raw: bytes | str | None = None
        # Primary: pikepdf's xmp_metadata attribute
        try:
            raw = self.pdf.xmp_metadata
        except Exception:
            raw = None
        # Fallback: read /Metadata stream directly from Root
        if not raw:
            try:
                meta_stream = self.pdf.Root.get("/Metadata")
                if meta_stream is not None and hasattr(meta_stream, "read_bytes"):
                    raw = meta_stream.read_bytes()
            except Exception:
                raw = None
        if not raw:
            return None
        try:
            if isinstance(raw, str):
                raw = raw.encode("utf-8", errors="replace")
            return etree.fromstring(raw)
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Metadata accessors (for M-signals)
    # ------------------------------------------------------------------
    def producer(self) -> str:
        val = self._get(self.info, "/Producer")
        return self._text(val)

    def creator(self) -> str:
        val = self._get(self.info, "/Creator")
        return self._text(val)

    def title(self) -> str:
        val = self._get(self.info, "/Title")
        return self._text(val)

    def document_lang(self) -> str:
        val = self._get(self.root, "/Lang")
        return self._text(val)

    def mark_info_marked(self) -> bool | None:
        mark_info = self._get(self.root, "/MarkInfo")
        return self._bool(mark_info, "/Marked")

    def is_linearised(self) -> bool:
        try:
            obj1 = self.pdf.get_object(1)
        except Exception:
            return False
        return obj1.get("/Linearized") is not None

    def xmp_history_events(self) -> list[dict[str, str]]:
        """Return a list of dicts with keys: action, software_agent."""
        if self.xmp_xml is None:
            return []
        ns = {
            "xmpMM": "http://ns.adobe.com/xap/1.0/mm/",
            "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
            "stEvt": "http://ns.adobe.com/xap/1.0/sType/ResourceEvent#",
        }
        events: list[dict[str, str]] = []
        # xmpMM:History / rdf:Seq / rdf:li
        for hist in self.xmp_xml.iter("{http://ns.adobe.com/xap/1.0/mm/}History"):
            for seq in hist.iter("{http://www.w3.org/1999/02/22-rdf-syntax-ns#}Seq"):
                for li in seq.iter("{http://www.w3.org/1999/02/22-rdf-syntax-ns#}li"):
                    evt: dict[str, str] = {}
                    action = li.find("stEvt:action", ns)
                    if action is not None and action.text:
                        evt["action"] = action.text
                    agent = li.find("stEvt:softwareAgent", ns)
                    if agent is not None and agent.text:
                        evt["software_agent"] = agent.text
                    if evt:
                        events.append(evt)
        return events

    def pdf_ua_part(self) -> int | None:
        if self.xmp_xml is None:
            return None
        for part in self.xmp_xml.iter("{http://www.aiim.org/pdfua/ns/id/}part"):
            if part.text:
                try:
                    return int(part.text)
                except ValueError:
                    return None
        return None

    # ------------------------------------------------------------------
    # Structure-tree accessors (for S-signals)
    # ------------------------------------------------------------------
    # Structure-tree accessors (for S-signals)
    # ------------------------------------------------------------------
    def struct_tree_root(self) -> pikepdf.Dictionary | None:
        return self._get(self.root, "/StructTreeRoot")

    def has_struct_tree(self) -> bool:
        root = self.struct_tree_root()
        if root is None:
            return False
        # Empty means no /K or /K is an empty array
        k = self._get(root, "/K")
        if k is None:
            return False
        if isinstance(k, pikepdf.Array) and len(k) == 0:
            return False
        return True

    def tag_tally(self) -> dict[str, int]:
        if self._tag_tally is not None:
            return self._tag_tally
        tally: dict[str, int] = {}
        root = self.struct_tree_root()
        if root is None:
            self._tag_tally = tally
            return tally
        self._walk_struct_tree(root, tally)
        self._tag_tally = tally
        return tally

    def _walk_struct_tree(self, node: Any, tally: dict[str, int]) -> None:
        children = self._get(node, "/K")
        if children is None:
            return
        if isinstance(children, pikepdf.Array):
            for child in children:
                self._visit_node(child, tally)
        else:
            self._visit_node(children, tally)

    def _visit_node(self, node: Any, tally: dict[str, int]) -> None:
        if isinstance(node, pikepdf.Dictionary):
            tag = self._get(node, "/S")
            if tag is not None:
                tag_name = self._text(tag)
                tally[tag_name] = tally.get(tag_name, 0) + 1
            self._walk_struct_tree(node, tally)
        elif isinstance(node, pikepdf.Object):
            # Indirect reference: follow it
            try:
                resolved = self.pdf.get_object(node.objgen)
                if isinstance(resolved, pikepdf.Dictionary):
                    tag = self._get(resolved, "/S")
                    if tag is not None:
                        tag_name = self._text(tag)
                        tally[tag_name] = tally.get(tag_name, 0) + 1
                    self._walk_struct_tree(resolved, tally)
            except Exception:
                pass

    def figure_alt_data(self) -> list[dict[str, Any]]:
        """Return list of dicts with keys: alt (str), has_alt (bool)."""
        if self._figures_with_alt is not None:
            return self._figures_with_alt
        result: list[dict[str, Any]] = []
        root = self.struct_tree_root()
        if root is None:
            self._figures_with_alt = result
            return result
        self._collect_figure_alt(root, result)
        self._figures_with_alt = result
        return result

    def _collect_figure_alt(self, node: Any, result: list[dict[str, Any]]) -> None:
        children = self._get(node, "/K")
        if children is None:
            return
        if isinstance(children, pikepdf.Array):
            for child in children:
                self._visit_figure_node(child, result)
        else:
            self._visit_figure_node(children, result)

    def _visit_figure_node(self, node: Any, result: list[dict[str, Any]]) -> None:
        if isinstance(node, pikepdf.Dictionary):
            tag = self._get(node, "/S")
            if tag is not None and self._text(tag) == "/Figure":
                alt = self._get(node, "/Alt")
                alt_text = self._text(alt)
                result.append({"alt": alt_text, "has_alt": alt is not None})
            self._collect_figure_alt(node, result)
        elif isinstance(node, pikepdf.Object):
            try:
                resolved = self.pdf.get_object(node.objgen)
                if isinstance(resolved, pikepdf.Dictionary):
                    tag = self._get(resolved, "/S")
                    if tag is not None and self._text(tag) == "/Figure":
                        alt = self._get(resolved, "/Alt")
                        alt_text = self._text(alt)
                        result.append({"alt": alt_text, "has_alt": alt is not None})
                    self._collect_figure_alt(resolved, result)
            except Exception:
                pass

    def table_th_data(self) -> list[dict[str, Any]]:
        """Return list of dicts with keys: scope (str or None)."""
        if self._tables_with_th is not None:
            return self._tables_with_th
        result: list[dict[str, Any]] = []
        root = self.struct_tree_root()
        if root is None:
            self._tables_with_th = result
            return result
        self._collect_th_data(root, result)
        self._tables_with_th = result
        return result

    def _collect_th_data(self, node: Any, result: list[dict[str, Any]]) -> None:
        children = self._get(node, "/K")
        if children is None:
            return
        if isinstance(children, pikepdf.Array):
            for child in children:
                self._visit_th_node(child, result)
        else:
            self._visit_th_node(children, result)

    def _visit_th_node(self, node: Any, result: list[dict[str, Any]]) -> None:
        if isinstance(node, pikepdf.Dictionary):
            tag = self._get(node, "/S")
            if tag is not None and self._text(tag) == "/TH":
                scope = self._get(node, "/Scope")
                result.append({"scope": self._text(scope) if scope else None})
            self._collect_th_data(node, result)
        elif isinstance(node, pikepdf.Object):
            try:
                resolved = self.pdf.get_object(node.objgen)
                if isinstance(resolved, pikepdf.Dictionary):
                    tag = self._get(resolved, "/S")
                    if tag is not None and self._text(tag) == "/TH":
                        scope = self._get(resolved, "/Scope")
                        result.append({"scope": self._text(scope) if scope else None})
                    self._collect_th_data(resolved, result)
            except Exception:
                pass

    def actual_text_issues(self) -> list[dict[str, Any]]:
        """Return list of dicts with keys: value (str), context (str)."""
        if self._actual_text_issues is not None:
            return self._actual_text_issues
        result: list[dict[str, Any]] = []
        root = self.struct_tree_root()
        if root is None:
            self._actual_text_issues = result
            return result
        self._collect_actual_text_issues(root, result)
        self._actual_text_issues = result
        return result

    def _collect_actual_text_issues(self, node: Any, result: list[dict[str, Any]]) -> None:
        children = self._get(node, "/K")
        if children is None:
            return
        if isinstance(children, pikepdf.Array):
            for child in children:
                self._visit_actual_text_node(child, result)
        else:
            self._visit_actual_text_node(children, result)

    def _visit_actual_text_node(self, node: Any, result: list[dict[str, Any]]) -> None:
        BAD = {"blank", "space", ""}
        if isinstance(node, pikepdf.Dictionary):
            actual = self._get(node, "/ActualText")
            if actual is not None:
                val = self._text(actual)
                if val in BAD:
                    result.append({"value": val, "context": "struct_node"})
            self._collect_actual_text_issues(node, result)
        elif isinstance(node, pikepdf.Object):
            try:
                resolved = self.pdf.get_object(node.objgen)
                if isinstance(resolved, pikepdf.Dictionary):
                    actual = self._get(resolved, "/ActualText")
                    if actual is not None:
                        val = self._text(actual)
                        if val in BAD:
                            result.append({"value": val, "context": "struct_node"})
                    self._collect_actual_text_issues(resolved, result)
            except Exception:
                pass

    def rolemap_entries(self) -> dict[str, str]:
        """Return dict of RoleMap entries, e.g. {'/StyleSpan': '/Span'}."""
        root = self.struct_tree_root()
        if root is None:
            return {}
        rolemap = self._get(root, "/RoleMap")
        if rolemap is None:
            return {}
        entries: dict[str, str] = {}
        if isinstance(rolemap, pikepdf.Dictionary):
            for key, val in rolemap.items():
                entries[self._text(key)] = self._text(val)
        return entries

    def has_thead(self) -> bool:
        """True if any /THead tag appears in the structure tree."""
        return self.tag_tally().get("/THead", 0) > 0

    def outlines_depth(self) -> int:
        """Return max depth of the /Outlines tree, 0 if absent or empty."""
        outlines = self._get(self.root, "/Outlines")
        if outlines is None:
            return 0
        try:
            return self._outline_depth(outlines, 1)
        except Exception:
            return 0

    def _outline_depth(self, node: Any, current: int) -> int:
        if not isinstance(node, pikepdf.Dictionary):
            return current
        first = self._get(node, "/First")
        if first is None:
            return current
        # Follow /First sibling chain
        max_depth = current + 1
        child = first
        while child is not None:
            if isinstance(child, pikepdf.Object):
                try:
                    child = self.pdf.get_object(child.objgen)
                except Exception:
                    break
            if not isinstance(child, pikepdf.Dictionary):
                break
            child_first = self._get(child, "/First")
            if child_first is not None:
                if isinstance(child_first, pikepdf.Object):
                    try:
                        child_first = self.pdf.get_object(child_first.objgen)
                    except Exception:
                        child_first = None
                if child_first is not None:
                    d = self._outline_depth(child_first, current + 1)
                    max_depth = max(max_depth, d)
            next_ref = self._get(child, "/Next")
            child = next_ref
        return max_depth

    # ------------------------------------------------------------------
    # Phase 2: paragraph text extraction (S3, S4)
    # ------------------------------------------------------------------
    def paragraph_texts(self) -> list[str]:
        """Return text content of every /P element in the structure tree."""
        result: list[str] = []
        root = self.struct_tree_root()
        if root is None:
            return result
        self._collect_paragraph_texts(root, result)
        return result

    def _collect_paragraph_texts(self, node: Any, result: list[str]) -> None:
        children = self._get(node, "/K")
        if children is None:
            return
        if isinstance(children, pikepdf.Array):
            for child in children:
                self._visit_paragraph_node(child, result)
        else:
            self._visit_paragraph_node(children, result)

    def _visit_paragraph_node(self, node: Any, result: list[str]) -> None:
        if isinstance(node, pikepdf.Dictionary):
            tag = self._get(node, "/S")
            if tag is not None and self._text(tag) == "/P":
                txt = self._node_text(node)
                if txt:
                    result.append(txt)
            self._collect_paragraph_texts(node, result)
        elif isinstance(node, pikepdf.Object):
            try:
                resolved = self.pdf.get_object(node.objgen)
                if isinstance(resolved, pikepdf.Dictionary):
                    tag = self._get(resolved, "/S")
                    if tag is not None and self._text(tag) == "/P":
                        txt = self._node_text(resolved)
                        if txt:
                            result.append(txt)
                    self._collect_paragraph_texts(resolved, result)
            except Exception:
                pass

    def _node_text(self, node: pikepdf.Dictionary) -> str:
        """Best-effort text extraction from a structure node, using /ActualText."""
        parts: list[str] = []
        children = self._get(node, "/K")
        if children is None:
            return ""
        if isinstance(children, pikepdf.Array):
            child_list = list(children)
        else:
            child_list = [children]
        for child in child_list:
            target = child
            if isinstance(target, pikepdf.Object):
                try:
                    target = self.pdf.get_object(target.objgen)
                except Exception:
                    continue
            if isinstance(target, pikepdf.Dictionary):
                actual = self._get(target, "/ActualText")
                if actual is not None:
                    parts.append(self._text(actual))
                else:
                    parts.append(self._node_text(target))
        return "".join(parts)

    # ------------------------------------------------------------------
    # Phase 2: artifact node detection (S9)
    # ------------------------------------------------------------------
    def artifact_nodes(self) -> list[dict[str, Any]]:
        """Return list of dicts representing /Artifact markings in the tree."""
        result: list[dict[str, Any]] = []
        root = self.struct_tree_root()
        if root is None:
            return result
        self._collect_artifact_nodes(root, result)
        return result

    def _collect_artifact_nodes(self, node: Any, result: list[dict[str, Any]]) -> None:
        children = self._get(node, "/K")
        if children is None:
            return
        if isinstance(children, pikepdf.Array):
            for child in children:
                self._visit_artifact_node(child, result)
        else:
            self._visit_artifact_node(children, result)

    def _visit_artifact_node(self, node: Any, result: list[dict[str, Any]]) -> None:
        if isinstance(node, pikepdf.Dictionary):
            self._record_if_artifact(node, result)
            self._collect_artifact_nodes(node, result)
        elif isinstance(node, pikepdf.Object):
            try:
                resolved = self.pdf.get_object(node.objgen)
                if isinstance(resolved, pikepdf.Dictionary):
                    self._record_if_artifact(resolved, result)
                    self._collect_artifact_nodes(resolved, result)
            except Exception:
                pass

    def _record_if_artifact(self, node: pikepdf.Dictionary, result: list[dict[str, Any]]) -> None:
        tag = self._get(node, "/S")
        if tag is not None and self._text(tag) == "/Artifact":
            result.append({"source": "tag", "subtype": None})
            return
        typ = self._get(node, "/Type")
        if typ is not None and self._text(typ) == "/Artifact":
            subtype = self._get(node, "/Subtype")
            result.append({"source": "type", "subtype": self._text(subtype) if subtype else None})

    # ------------------------------------------------------------------
    # Phase 2: span-level Lang attribute count (S11)
    # ------------------------------------------------------------------
    def span_lang_count(self) -> int:
        """Count /Span structure elements that carry a /Lang attribute."""
        root = self.struct_tree_root()
        if root is None:
            return 0
        return self._count_span_lang(root, 0)

    def _count_span_lang(self, node: Any, count: int) -> int:
        children = self._get(node, "/K")
        if children is None:
            return count
        if isinstance(children, pikepdf.Array):
            for child in children:
                count = self._visit_span_lang_node(child, count)
        else:
            count = self._visit_span_lang_node(children, count)
        return count

    def _visit_span_lang_node(self, node: Any, count: int) -> int:
        target = node
        if isinstance(target, pikepdf.Object):
            try:
                target = self.pdf.get_object(target.objgen)
            except Exception:
                return count
        if isinstance(target, pikepdf.Dictionary):
            tag = self._get(target, "/S")
            is_span = tag is not None and self._text(tag) == "/Span"
            if is_span and self._get(target, "/Lang") is not None:
                count += 1
            count = self._count_span_lang(target, count)
        return count

    # ------------------------------------------------------------------
    # Phase 2: StructParents completeness check (S12)
    # ------------------------------------------------------------------
    def struct_parents_ok(self) -> bool:
        """Return True when every page with content has /StructParents AND the
        StructTreeRoot has a well-formed /ParentTree.
        """
        struct_tree = self.struct_tree_root()
        if struct_tree is None:
            return False
        if self._get(struct_tree, "/ParentTree") is None:
            return False
        pages = self._get(self.root, "/Pages")
        if pages is None:
            return False
        return self._check_pages_struct_parents(pages)

    def _check_pages_struct_parents(self, node: Any) -> bool:
        target = node
        if isinstance(target, pikepdf.Object):
            try:
                target = self.pdf.get_object(target.objgen)
            except Exception:
                return False
        if not isinstance(target, pikepdf.Dictionary):
            return True
        node_type = self._text(target.get("/Type")) if target.get("/Type") is not None else ""
        if node_type == "/Page":
            has_content = (
                self._get(target, "/Contents") is not None
                or self._get(target, "/Resources") is not None
            )
            if has_content and self._get(target, "/StructParents") is None:
                return False
            return True
        if node_type == "/Pages":
            kids = self._get(target, "/Kids")
            if kids is None:
                return True
            if isinstance(kids, pikepdf.Array):
                for kid in kids:
                    if not self._check_pages_struct_parents(kid):
                        return False
            return True
        return True

    # ------------------------------------------------------------------
    # Phase 3: reading-order analysis (S13, S14)
    # ------------------------------------------------------------------
    def mcid_content_order(self, page_index: int) -> list[int]:
        """Return MCIDs in content-stream order for the given page.

        For authoring-tool exports, this order reflects text-frame drawing
        order. For remediated PDFs the same order persists in the content
        stream; what changes is the tree order.
        """
        if page_index >= len(self.pdf.pages):
            return []
        page = self.pdf.pages[page_index]
        mcids: list[int] = []
        try:
            for ops, op in pikepdf.parse_content_stream(page):
                if str(op) in ("BDC", "BMC") and len(ops) >= 2:
                    props = ops[1]
                    if isinstance(props, pikepdf.Dictionary):
                        mcid = props.get("/MCID")
                        if mcid is not None:
                            try:
                                mcids.append(int(mcid))
                            except (TypeError, ValueError):
                                pass
        except Exception:
            return []
        return mcids

    def mcid_tree_order_by_page(self) -> dict[int, list[int]]:
        """Return MCIDs per page in structure-tree pre-order traversal order."""
        result: dict[int, list[int]] = {}
        root = self.struct_tree_root()
        if root is None:
            return result
        # Build page object -> page index map
        page_to_idx: dict[Any, int] = {}
        for idx, page in enumerate(self.pdf.pages):
            page_to_idx[page.unparse()] = idx
        self._walk_tree_for_mcids(root, None, page_to_idx, result)
        return result

    def _walk_tree_for_mcids(
        self,
        node: Any,
        current_page: int | None,
        page_to_idx: dict[Any, int],
        result: dict[int, list[int]],
    ) -> None:
        target = node
        if isinstance(target, pikepdf.Object):
            try:
                target = self.pdf.get_object(target.objgen)
            except Exception:
                return
        if not isinstance(target, pikepdf.Dictionary):
            return
        # Track /Pg if present
        pg = self._get(target, "/Pg")
        if pg is not None:
            try:
                current_page = page_to_idx.get(pg.unparse(), current_page)
            except Exception:
                pass
        children = self._get(target, "/K")
        if children is None:
            return
        if not isinstance(children, pikepdf.Array):
            children = [children]
        for child in children:
            # Integer child = direct MCID reference under the parent's /Pg
            if isinstance(child, int) and current_page is not None:
                result.setdefault(current_page, []).append(child)
            elif isinstance(child, pikepdf.Dictionary):
                # /Type /MCR struct ref?
                ctype = self._get(child, "/Type")
                if ctype is not None and self._text(ctype) == "/MCR":
                    mcid = self._get(child, "/MCID")
                    page_ref = self._get(child, "/Pg")
                    if page_ref is not None:
                        try:
                            page_idx = page_to_idx.get(page_ref.unparse(), current_page)
                        except Exception:
                            page_idx = current_page
                    else:
                        page_idx = current_page
                    if mcid is not None and page_idx is not None:
                        try:
                            result.setdefault(page_idx, []).append(int(mcid))
                        except (TypeError, ValueError):
                            pass
                else:
                    self._walk_tree_for_mcids(child, current_page, page_to_idx, result)
            else:
                self._walk_tree_for_mcids(child, current_page, page_to_idx, result)

    def reading_order_match_ratio(self) -> tuple[float, int]:
        """Return (avg_match_ratio, pages_compared).

        For each page, compare MCID sequence in tree order vs content-stream
        order. Match ratio is the fraction of MCIDs that appear at the same
        index in both lists, computed only on the prefix common to both.
        Returns 0.0 if no MCIDs found on any page.
        """
        tree_by_page = self.mcid_tree_order_by_page()
        if not tree_by_page:
            return (0.0, 0)
        ratios: list[float] = []
        for page_idx, tree_mcids in tree_by_page.items():
            content_mcids = self.mcid_content_order(page_idx)
            if not tree_mcids or not content_mcids:
                continue
            common_len = min(len(tree_mcids), len(content_mcids))
            if common_len == 0:
                continue
            matches = sum(
                1
                for i in range(common_len)
                if tree_mcids[i] == content_mcids[i]
            )
            ratios.append(matches / common_len)
        if not ratios:
            return (0.0, 0)
        return (sum(ratios) / len(ratios), len(ratios))

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------
    def close(self) -> None:
        self.pdf.close()

    def __enter__(self) -> PdfInspector:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
