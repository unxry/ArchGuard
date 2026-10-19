# Независимый аудит целостности Word-файла

Результат: **PASS**. Артефакт: `docs/thesis/ArchGuard_AI_VKR_MASTER.docx`.
SHA-256: `71e83609e42e0592a5cd19a5b148799d5ba407fe6cdc2bd4771cb1c0b4202169`.
Проверки: PASS=68, FAIL=0, INFO=2.

Аудитор читает ZIP/OOXML и новые публичные авторские материалы. Он не изменяет Word-файл, не открывает приватные случаи и не запускает научные вычисления. Проверены все XML-части, связи, поля, закладки, формулы, источники и явно сохраненные отрицательные результаты.

Геометрия и стили проверены по OOXML. Эта проверка не подтверждает визуальную верстку: ее завершает отдельное чтение отрендеренных страниц. Административные поля [ЗАПОЛНИТЬ: …] сохранены явно и не выданы за подписи или установленные сведения.

| Проверка | Результат |
|---|---|
| artifact_exists | PASS |
| zip_integrity | PASS |
| zip_unique_members | PASS |
| zip_safe_member_names | PASS |
| no_junk_macros_comments_embedded_objects | PASS |
| all_xml_parts_parse | PASS |
| public_safe_package_text | PASS |
| embedded_media_count | PASS |
| media_nonempty | PASS |
| relationship_targets_resolve | PASS |
| all_parts_have_content_types | PASS |
| every_image_embedded_and_used | PASS |
| required_ooxml_parts | PASS |
| no_revisions_comments_objects | PASS |
| no_hidden_text | PASS |
| field_structure_balanced | PASS |
| required_native_fields | PASS |
| bookmark_names_unique | PASS |
| bookmark_pairs_complete | PASS |
| native_references_resolve | PASS |
| confirmed_admin_author | PASS |
| confirmed_admin_department | PASS |
| confirmed_admin_group | PASS |
| confirmed_admin_supervisor | PASS |
| no_cached_field_errors | PASS |
| fields_update_on_open | PASS |
| section_1_geometry | PASS |
| section_2_geometry | PASS |
| section_3_geometry | PASS |
| section_4_geometry | PASS |
| section_5_geometry | PASS |
| section_6_geometry | PASS |
| section_7_geometry | PASS |
| section_8_geometry | PASS |
| portrait_and_landscape_sections | PASS |
| style_Normal | PASS |
| style_Heading1 | PASS |
| style_Heading2 | PASS |
| style_Heading3 | PASS |
| style_TableText | PASS |
| style_Equation | PASS |
| style_Bibliography | PASS |
| eight_editable_omml_equations | PASS |
| math_no_source_tex_commands | PASS |
| native_math_fractions | PASS |
| no_unexpanded_authoring_markers | PASS |
| administrative_placeholders | INFO |
| manuscript_sources_present | PASS |
| 65_verified_source_citations | PASS |
| code_examples_preserved_verbatim | PASS |
| bibliography_matches_verified_entries | PASS |
| all_numeric_citations_resolve_and_match | PASS |
| all_caption_bookmarks_resolve | PASS |
| source_equation_count | PASS |
| docx_build_source_snapshot_current | PASS |
| negative_presence_feature_leakage_retained | PASS |
| negative_presence_natural_oss_no_positives | PASS |
| negative_presence_context_quality_decrease | PASS |
| negative_presence_architecture_error_retained | PASS |
| negative_presence_provider_missing_retained | PASS |
| negative_presence_security_positive_nondefinitive | PASS |
| negative_presence_security_negative_nondefinitive | PASS |
| negative_presence_security_no_definitive_negatives | PASS |
| negative_presence_security_final_decline | PASS |
| negative_presence_no_blind_v2_final_baseline | PASS |
| negative_presence_invoice_not_measured | PASS |
| negative_presence_not_production_claim | PASS |
| overclaim_context_review | PASS |
| scientific_review_boundary | INFO |
| build_manifest_artifact_hash | PASS |

Полные параметры, числители проверок и снимки исходников: `internal/docx-audit.json`.

Научная проверка агрегатов и ограничений: `THESIS_FACT_AUDIT.md`; приложение Е независимо сверено по 179 числовым ячейкам в `internal/appendix-e-review.json`.
