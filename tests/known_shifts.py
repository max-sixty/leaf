"""The tests whose pages still make a layout shift `shift_watch.js` fails, each a defect
waiting on its fix (`render_harness.clean_browser`).

`KNOWN_UNASKED` names, by file and function whatever its parameters, the tests whose
pages make a shift without input, with a comment naming what a survey saw move there
for whoever takes up the defect. `KNOWN_CARRIES` names the tests whose typing carries
its field, by the report. Fixing one deletes its line. A test joins only as a defect to
fix, never as behavior to keep (`tests/AGENTS.md`, "Consume a browser error where it is
caused").

The lists come from a complete run (`--run-nightly`) with them empty, and from a nightly
run on Linux CI. Chrome reports a shift only where one paints, so a test that a loaded
machine renders differently can join later."""

KNOWN_UNASKED = {
    "test_chrome_contracts.py": {
        # button.lf-shortcut-more
        "test_a_repaint_unsettles_the_rendering_until_it_lands",
        # details.lf-thread-compact.lf-thread
        "test_incoming_reply_follows_a_selected_thread_before_later_cards",
    },
    "test_render_aim.py": {
        # aside#lf-margin-preview.lf-ui.lf-margin-preview
        "test_a_declared_flowchart_node_keeps_its_comment_across_renderings",
        # span.lf-shortcut
        "test_a_draft_below_its_passage_keeps_its_lane_whatever_it_holds",
        # span.lf-shortcut
        "test_a_side_comment_grows_down_from_the_line_it_was_opened_on",
        # div.lf-ui.lf-fab-bar.lf-target-paint
        "test_a_text_comment_chooses_above_when_the_page_has_more_room_there",
        # span.lf-margin-marker.lf-ui.lf-margin-entry
        "test_a_visual_part_mark_follows_its_drawn_svg_shape",
    },
    "test_render_anchors.py": {
        # button.lf-shortcut-more
        "test_a_diff_anchors_to_the_side_it_was_read_on",
        # button.lf-shortcut-more
        "test_a_diff_is_colored_by_each_files_own_path",
        # http://127.0.0.1:44091/versions/v1.html: a node since removed
        "test_a_diff_surface_keeps_the_complete_thread_lifecycle_inline",
        # button.lf-shortcut-more
        "test_a_passage_among_padded_emoji_confirms_its_neighbours",
        # leaf-margin-cluster.lf-ui.lf-margin-cluster
        "test_a_quote_finds_its_passage_whatever_its_whitespace",
        # button.lf-shortcut-more, span.lf-shortcut
        "test_a_removed_subject_keeps_its_thread_open_and_detached",
        # button.lf-shortcut-more
        "test_a_repeated_passage_anchors_where_it_was_picked",
        # button.lf-shortcut-more
        "test_a_repeated_passage_at_an_edge_anchors_where_it_was_picked",
        # button.lf-shortcut-more, span.lf-shortcut
        "test_an_ambiguous_revised_passage_detaches_until_the_agent_moves_it",
        # leaf-margin-cluster.lf-ui.lf-margin-cluster
        "test_an_id_staged_into_a_shadow_tree_is_still_the_pages_id",
        # leaf-margin-cluster.lf-ui.lf-margin-cluster
        "test_an_open_composer_does_not_eat_the_next_click",
        # button.lf-shortcut-more
        "test_browser_and_file_captures_stop_at_the_same_widget_fences",
        # leaf-margin-cluster.lf-ui.lf-margin-cluster
        "test_code_is_colored_without_a_word_moving",
        # button.lf-ui.lf-margin-entry.lf-react-mark
        "test_every_mark_the_layer_paints_on_words_is_seen_against_the_paper",
        # div.lf-ui.lf-response-control.lf-thread-transition, button.lf-shortcut-more
        "test_one_neighbour_is_not_enough_to_identify_a_revised_comment",
        # leaf-margin-cluster.lf-ui.lf-margin-cluster
        "test_pending_comparison_moves_with_a_live_revision",
        # button.lf-shortcut-more
        "test_quotes_cross_preserving_containers_and_remain_attached",
        # div.lf-ui.lf-fab-bar.lf-target-paint
        "test_real_page_passages_can_be_quoted",
        # button.lf-shortcut-more
        "test_staged_widget_controls_name_the_presses_their_owners_make",
        # leaf-margin-cluster.lf-ui.lf-margin-cluster
        "test_the_pointer_stops_claiming_a_mark_it_scrolled_past",
    },
    "test_render_application_boundary.py": {
        # leaf-margin-cluster.lf-ui.lf-margin-cluster
        "test_current_readiness_releases_a_connected_page_widget",
    },
    "test_render_commands.py": {
        # main.layout-column, button.lf-shortcut-more
        "test_a_shot_compares_its_frames_with_a_direct_divider",
        # lf-option#x-dome, form.lf-another.lf-ui
        "test_the_gate_measures_an_inline_widget_by_its_words",
    },
    "test_render_controls.py": {
        # span.lf-shortcut, button.lf-shortcut-more
        "test_a_closed_leaf_clears_itself_off_the_drawer",
        # p#p4, p#p0
        "test_a_closing_layer_hands_the_user_back_to_the_first_place_that_takes_them",
        # a.lf-others-row, span.lf-dot.working
        "test_a_leaves_update_is_presented_before_the_page_calls_it_current",
        # span.lf-shortcut, button.lf-shortcut-more
        "test_a_panel_row_follows_its_pages_status_live",
        # button.lf-shortcut-more
        "test_a_recorded_move_is_acknowledged_in_the_status_and_nowhere_else",
        # span.lf-shortcut, button.lf-shortcut-more
        "test_a_walk_down_the_drawer_stops_clear_of_the_shortcut_bar_text",
        # h3.lf-vr-case-title, div.lf-banner-actions
        "test_each_control_archetype_holds_its_neighbours_still",
        # a.lf-others-row, span.lf-dot.working
        "test_leaves_keep_focus_through_reordering_and_choose_a_neighbour_on_removal",
        # span.lf-margin-marker.lf-ui.lf-margin-entry, lf-sample#second-practice
        "test_live_samples_keep_real_gestures_and_drafts_inside_the_child",
        # lf-sample#second-practice
        "test_live_samples_release_pending_allocations_and_can_reconnect",
        # lf-sample#second-practice
        "test_live_samples_retire_before_navigation_and_coalesce_reset",
        # details.lf-thread-compact.lf-thread, span.lf-shortcut
        "test_product_gallery_threads_tab_operates_seeded_panel_views",
        # lf-board#feeders, p#insert
        "test_the_poll_leaves_the_banner_where_it_was",
        # span.lf-key-badge.lf-ask-binding-badge, button.lf-shortcut-more
        "test_the_ring_reading_distinguishes_element_marks_from_focus",
        # span.lf-key-badge.lf-ask-binding-badge, button.lf-shortcut-more
        "test_the_ring_reading_names_every_way_a_box_can_draw_nothing_past_its_edge",
        # section#rn-console-section, section#rn-api-section
        "test_the_ring_reading_sees_and_measures_a_ring_cast_as_a_shadow",
        # span.lf-shortcut, button.lf-shortcut-more
        "test_thread_panel_gallery_shows_independent_live_views",
    },
    "test_render_drafts.py": {
        # h2#notes, p#p-filler
        "test_a_draft_wait_only_paints_after_the_shared_busy_delay",
        # h2#notes, p#intro
        "test_an_empty_draft_survives_reload_and_blocks_a_version_switch",
        # div.lf-say.lf-ui, div.lf-compose-field
        "test_an_older_settlement_cannot_erase_a_newer_failed_write",
        # div.lf-thread-panel-foot
        "test_failed_settlement_keeps_the_base_for_a_chained_nondurable_edit",
        # button.lf-shortcut-more
        "test_page_round_trip",
        # div.lf-say.lf-ui, div.lf-compose-field
        "test_poll_settlement_cannot_tombstone_a_newer_durable_generation",
        # span.lf-shortcut
        "test_two_passages_hold_two_composer_drafts",
    },
    "test_render_drawing.py": {
        # svg.lf-drawing-mark.lf-drawing-pending
        "test_a_drawing_can_begin_on_page_whitespace",
        # span.lf-shortcut
        "test_a_malformed_anchored_drawing_draft_keeps_its_words_without_the_mark",
        # span.lf-shortcut
        "test_an_unsent_drawing_survives_reload_before_it_has_words",
    },
    "test_render_export.py": {
        # main.layout-column
        "test_a_gloss_keeps_its_explanation_in_print",
        # a node since removed, main.layout-column
        "test_inline_threads_keep_their_words_without_live_controls_in_print",
    },
    "test_render_gate.py": {
        # h3.lf-vr-case-title
        "test_a_closed_surface_leaves_the_page_as_it_found_it",
        # h3.lf-vr-case-title
        "test_a_page_at_rest_does_nothing",
        # li in ol in div.lf-toc-rows, lf-tab#bg-view-interactions
        "test_a_page_hands_its_note_strip_back_when_the_panel_takes_the_room",
        # button.lf-btn.lf-auxiliary-toggle.lf-threads-toggle
        "test_a_resized_page_comes_back_as_it_was",
        # p#left
        "test_a_row_at_a_frame_edge_holds_the_trim_by_declaring_it",
        # h3.lf-vr-case-title
        "test_a_scroll_writes_only_what_it_changes",
        # h2#padded-heading, p in main.layout-column
        "test_frame_edges_pass_through_whatever_stands_at_them",
        # dialog#lf-threads.lf-ui.lf-thread-panel.open, div.lf-ui.lf-edge
        "test_page_fixture_renders",
    },
    "test_render_margin.py": {
        # button.lf-shortcut-more
        "test_a_page_that_can_grow_margin_status_reserves_its_rail_before_the_first_gesture",
        # span.lf-margin-entry-label
        "test_an_acknowledgment_uses_status_until_an_active_claim_restores_a_disclosure",
        # span.lf-key-badge.lf-ask-binding-badge
        "test_ask_binding_badges_follow_the_feature_gallery_s_visible_margin_entries",
        # span.lf-margin-entry-label
        "test_margin_entry_tone_stays_distinct_from_control_and_agent_state",
        # button.lf-ui.lf-margin-entry, leaf-margin-cluster.lf-ui.lf-margin-cluster
        "test_margin_projection_keeps_opaque_owner_and_entry_identities_distinct",
        # button.lf-ui.lf-margin-entry, leaf-margin-cluster.lf-ui.lf-margin-cluster
        "test_secondary_margin_entry_proxies_preserve_disabled_and_focus_contract",
        # button.lf-shortcut-more, span.lf-shortcut
        "test_the_feature_gallery_carries_a_margin_entry_through_its_whole_lifecycle",
        # span.lf-margin-marker.lf-ui.lf-margin-entry
        "test_unit_claim_arrivals_share_one_window_with_the_open_page_map",
    },
    "test_render_navigation.py": {
        # leaf-margin-cluster.lf-ui.lf-margin-cluster
        "test_a_comment_leaves_its_block_as_the_page_wrote_it",
        # figure#fig, h1#t
        "test_a_focused_scope_owns_its_declared_key_while_the_command_is_unavailable",
        # span.lf-key-badge.lf-key-hint.lf-go-to-hint
        "test_a_generated_hint_is_never_drawn_on_the_key_line",
        # button.lf-shortcut-more
        "test_a_label_press_keeps_the_controls_keyboard_standing",
        # figure#fig, h1#t
        "test_a_partially_shadowed_row_keeps_each_other_live_binding",
        # div.lf-ui.lf-target-trace.lf-target-paint
        "test_a_thread_walk_card_leaves_and_returns_with_its_anchor",
        # button.lf-shortcut-more
        "test_a_widget_that_renames_its_role_keeps_the_press_offer_gave_it",
        # button.lf-shortcut-more
        "test_an_asks_pick_stays_a_place_to_stand_after_the_answer",
        # button.lf-shortcut-more
        "test_an_inline_tab_keeps_its_panel_inside_one_visible_boundary",
        # button.lf-shortcut-more
        "test_c_in_a_seated_thread_reaches_the_thread_it_is_in",
        # leaf-margin-cluster.lf-ui.lf-margin-cluster
        "test_closing_the_panel_puts_down_the_card_it_was_lighting",
        # span.lf-key-badge.lf-key-hint.lf-go-to-hint
        "test_generated_hints_follow_the_page_while_it_moves",
        # button.lf-shortcut-more
        "test_native_top_layers_bound_the_keyboard_stack",
        # button.lf-shortcut-more
        "test_radio_and_slider_keys_stay_with_the_control_inside_a_modal",
        # button.lf-shortcut-more
        "test_the_arrows_say_which_way_the_section_under_the_user_goes",
        # span.lf-key-badge.lf-ask-binding-badge
        "test_the_feature_gallery_exercises_core_user_workflows",
        # span.lf-margin-marker.lf-ui.lf-margin-entry, p#bg-thread-text
        "test_the_feature_gallery_exercises_the_injected_core_surfaces",
        # li in ol in div.lf-toc-rows, section#bg-window-practice
        "test_the_feature_gallery_sections_are_stable_preview_destinations",
        # lf-tabs#bg-tabs.lf-rendered, p in main.layout-column
        "test_the_gallery_tab_set_uses_the_boundary_of_its_composition",
        # leaf-margin-cluster.lf-ui.lf-margin-cluster
        "test_the_page_marks_the_comment_the_user_is_standing_in",
        # leaf-margin-cluster.lf-ui.lf-margin-cluster
        "test_the_pointer_over_a_comment_lights_the_passage_it_is_about",
        # a node since removed
        "test_the_pr_walkthrough_exercises_an_inline_diff_thread",
        # span.lf-shortcut, button.lf-shortcut-more
        "test_workspace_posture_changes_keep_each_panes_reading",
    },
    "test_render_options.py": {
        # lf-ask#tools-decision
        "test_a_multiple_page_ask_waits_for_done",
        # leaf-margin-cluster.lf-ui.lf-margin-cluster, span.lf-margin-entry-label
        "test_a_widget_without_a_thread_says_what_the_agent_is_doing",
        # leaf-margin-cluster.lf-ui.lf-margin-cluster
        "test_local_work_chrome_does_not_take_its_holder_gesture",
        # lf-diff#patch.lf-rendered, span.lf-margin-marker.lf-ui.lf-margin-entry
        "test_settled_widget_work_leaves_a_declared_shadow_tree",
        # button.lf-shortcut-more
        "test_what_a_widget_paints_it_says_to_a_user_listening",
        # lf-diff#patch.lf-rendered, span.lf-margin-marker.lf-ui.lf-margin-entry
        "test_widget_work_keeps_its_button_style_in_a_declared_shadow_tree",
    },
    "test_render_options_addition.py": {
        # lf-ask#bracket-decision, section#sec-mounts
        "test_an_add_field_reconnects_to_its_shared_draft",
        # leaf-margin-cluster.lf-ui.lf-margin-cluster
        "test_an_arrival_cannot_hide_a_question_draft",
        # button.lf-shortcut-more
        "test_an_option_mark_keeps_addition_and_clarification_as_separate_routes",
    },
    "test_render_options_settled.py": {
        # main.layout-column
        "test_a_printed_page_says_which_option_carries_the_pick",
        # button.lf-shortcut-more
        "test_settled_options_collapse_without_going_out_of_reach",
    },
    "test_render_outbox.py": {
        # span.lf-shortcut
        "test_a_draft_that_outlives_its_passage_returns_with_that_passage",
        # leaf-banner-approval-face in button.lf-btn.primary.lf-signoff
        "test_a_failed_candidate_presentation_keeps_version_approval",
        # leaf-margin-cluster.lf-ui.lf-margin-cluster
        "test_a_lost_accepted_response_keeps_later_gestures_in_order",
        # button.lf-shortcut-more
        "test_a_move_on_a_version_a_newer_one_replaced_is_refused_and_restored",
        # button.lf-shortcut-more
        "test_a_pointer_drag_stops_the_line_offering_the_press_it_refuses",
        # lf-card#card-third, lf-card#card-heater
        "test_a_refused_position_restores_the_complete_sibling_order",
        # lf-board#feeders, p#insert
        "test_a_second_tab_takes_the_decision_back_too",
        # leaf-margin-cluster.lf-ui.lf-margin-cluster
        "test_a_server_that_cannot_take_a_gesture_yet_says_so_and_keeps_it",
        # lf-option-control.lf-pick.lf-ui
        "test_a_withdrawal_is_heard_by_a_tab_reading_a_later_version",
        # leaf-margin-cluster.lf-ui.lf-margin-cluster
        "test_a_withdrawal_restores_what_still_stands_not_what_stood_then",
        # lf-ask#picks-decision
        "test_a_withdrawal_waits_for_a_widget_that_cannot_take_it_yet",
        # lf-column#outer-done, leaf-margin-cluster.lf-ui.lf-margin-cluster
        "test_an_outer_refusal_preserves_a_different_nested_widgets_state",
        # leaf-margin-cluster.lf-ui.lf-margin-cluster
        "test_one_supplied_attempt_cannot_name_two_queued_actions",
        # span.lf-shortcut
        "test_the_composer_never_stands_on_its_own_mark",
        # button.lf-ui.lf-margin-entry.lf-sug-accept
        "test_undo_preserves_the_place_and_restores_passage_marks",
    },
    "test_render_pages.py": {
        # leaf-banner-status.lf-banner-status
        "test_a_box_that_shows_less_than_it_holds_says_so",
        # div.lf-compose-field
        "test_a_failed_agent_root_restores_the_focused_first_message_composer",
        # div.lf-page-thread-msg.lf-ui.user
        "test_a_failed_resolution_restores_a_focused_inline_reply",
        # p#p-original
        "test_a_failed_state_keeps_focus_in_the_open_versions_menu",
        # p#p-original
        "test_a_reply_notice_survives_a_failed_state_and_keeps_its_agent",
        # p#p-original, leaf-margin-cluster.lf-ui.lf-margin-cluster
        "test_a_written_anchor_keeps_its_copy_when_the_page_grows_another",
        # section#wide, table#table
        "test_authored_blocks_choose_column_wide_or_available_space",
        # lf-board#sprint, main.layout-column
        "test_paper_keeps_the_column",
        # main.layout-column, lf-tab#corpus-triage-board
        "test_paper_takes_the_press_off_everything_it_cannot_press",
        # lf-board#plan
        "test_the_room_follows_a_margin_taken_after_the_handover",
    },
    "test_render_projection.py": {
        # button.lf-shortcut-more, p in main.layout-column
        "test_a_paragraph_inserted_above_the_user_does_not_shift_the_ones_below",
        # leaf-margin-cluster.lf-ui.lf-margin-cluster
        "test_a_part_and_its_own_widget_keep_same_named_verbs_independent",
        # leaf-margin-cluster.lf-ui.lf-margin-cluster
        "test_a_projected_attribute_opens_an_ask_captured_from_authored_markup",
        # button.lf-shortcut-more
        "test_a_prose_revision_takes_only_the_words_it_rewrote",
        # button.lf-shortcut-more
        "test_a_range_the_user_moved_keeps_its_place_across_a_revision",
        # p in lf-ranked#services
        "test_a_reordered_projection_keeps_the_user_in_the_row_they_stand_in",
        # p#lk-para, button.lf-shortcut-more
        "test_a_restated_ask_returns_a_user_to_the_question_not_to_a_control",
        # leaf-margin-cluster.lf-ui.lf-margin-cluster, button.lf-shortcut-more
        "test_a_revision_inside_one_tab_keeps_the_tab_set_and_every_other_tab",
        # button.lf-shortcut-more
        "test_a_revision_replaces_the_widget_it_rewrote_and_keeps_the_one_it_did_not",
        # main.layout-sidebar, section.panel.lf-fleet-view
        "test_a_roster_row_names_its_target_without_saying_it_twice",
        # span.lf-heard
        "test_a_rosters_clock_keeps_moving_when_the_server_stops_answering",
        # lf-agent#ag-finch, lf-agent#ag-siskin
        "test_a_rosters_row_says_when_the_log_last_heard_from_that_worker",
        # lf-agent#ag-siskin, span.lf-heard
        "test_a_rosters_row_survives_the_polls_that_keep_it_fresh",
        # button.lf-shortcut-more
        "test_a_source_replacement_preserves_the_focused_draft_and_its_original_anchor",
        # button.lf-btn.lf-auxiliary-toggle.lf-threads-toggle, div.lf-banner-actions
        "test_a_stamped_live_draft_and_its_unstamped_view_keep_distinct_menu_rows",
        # button.lf-btn.lf-auxiliary-toggle.lf-threads-toggle, div.lf-banner-actions
        "test_a_stamped_url_stays_pinned_while_the_live_root_follows_a_draft",
        # button.lf-btn.lf-auxiliary-toggle.lf-threads-toggle, div.lf-banner-actions
        "test_a_widget_textarea_holds_an_arriving_live_version",
        # p#lk-para, button.lf-shortcut-more
        "test_a_withdrawn_ask_leaves_the_user_on_the_page",
        # span.lf-heard
        "test_a_worker_that_has_never_reported_dates_from_its_version",
        # div.lf-banner-actions
        "test_an_old_document_state_request_cannot_update_the_new_revision",
        # div.lf-ui.lf-fab-bar.lf-target-paint, button.lf-shortcut-more
        "test_another_kind_of_sibling_above_an_edited_paragraph_keeps_the_user_on_it",
        # details.lf-call-group, button.lf-shortcut-more
        "test_call_diff_keeps_the_user_on_a_row_a_new_capture_moves",
        # lf-agent#ag-finch, lf-agent#ag-siskin
        "test_claims_and_reports_share_one_canonical_update_feed",
        # span.lf-margin-marker.lf-ui.lf-margin-entry
        "test_command_hub_an_absorbed_input_stays_fulfilled",
        # li.lf-activity-row, p.lf-activity-excerpt
        "test_command_hub_keeps_projection_focus_when_unrelated_news_arrives",
        # section#hub-record.panel, li.lf-activity-row
        "test_command_hub_readings_follow_their_seat_across_revisions",
        # td.lf-pr-check-status, button.lf-shortcut-more
        "test_pr_review_package_keeps_the_authors_brief_distinct_and_stable",
        # lf-new in lf-suggestion#sug-refill
        "test_replay_signatures_exclude_settlement_and_other_runtime_paint",
        # lf-agent#ag-finch, lf-agent#ag-siskin
        "test_report_words_and_widget_state_wait_together_for_a_drag",
        # main.layout-workspace
        "test_revision_does_not_move_a_page_offset_into_a_new_bounded_region",
        # span.lf-shortcut, button.lf-shortcut-more
        "test_revision_does_not_move_an_offset_between_bounded_region_owners",
        # main.layout-column
        "test_revision_remembers_the_active_region_when_a_workspace_reflows",
        # span.lf-shortcut, button.lf-shortcut-more
        "test_revision_reveals_a_page_landmark_around_an_empty_active_region",
        # span.lf-shortcut, button.lf-shortcut-more
        "test_revision_reveals_an_active_region_without_any_reading_landmark",
        # section#recent, li.lf-activity-row
        "test_the_activity_feed_words_a_pick_in_the_document_it_was_made_in",
        # button.lf-btn.lf-auxiliary-toggle.lf-threads-toggle, div.lf-banner-actions
        "test_the_live_page_defers_for_typing_then_adopts_without_a_press",
        # leaf-margin-cluster.lf-ui.lf-margin-cluster
        "test_the_render_gate_reads_a_page_that_has_finished_arriving",
        # h3.lf-vr-case-title
        "test_visual_review_controls_keep_keyboard_navigation_local",
        # h3.lf-vr-case-title
        "test_visual_review_discloses_focus_without_distorting_unsupported_browsers",
        # h3.lf-vr-case-title
        "test_visual_review_gallery_gives_a_laptop_to_the_evidence",
        # h3.lf-vr-case-title
        "test_visual_review_guides_one_typed_still_run",
        # h3.lf-vr-case-title
        "test_visual_review_ignores_a_late_load_from_detached_evidence",
        # button.lf-shortcut-more
        "test_worktree_evidence_names_the_arrow_that_stands_on_it",
        # lf-ask#cz-ask, leaf-margin-cluster.lf-ui.lf-margin-cluster
        "test_z_takes_back_a_decision_carried_into_a_later_revision",
    },
    "test_render_reactions.py": {
        # span.lf-shortcut
        "test_a_response_draft_yields_focus_when_the_panel_leaves_no_usable_room",
        # button.lf-visual-action.lf-quiet.lf-ui
        "test_a_selection_change_replaces_and_clears_a_visual_target",
        # button.lf-visual-action.lf-quiet.lf-ui
        "test_a_visual_proxy_keeps_user_standing_across_provider_updates",
        # lf-diagram#flow.lf-rendered, button.lf-visual-action.lf-quiet.lf-ui
        "test_a_visual_proxy_resolves_a_rebuilt_part_and_reveals_it_on_focus",
        # button.lf-visual-action.lf-quiet.lf-ui
        "test_one_semantic_visual_target_gets_one_keyboard_proxy",
        # button.lf-visual-action.lf-quiet.lf-ui, button.lf-shortcut-more
        "test_visual_proxies_keep_focus_when_one_shadow_host_is_repainted",
    },
    "test_render_read_state.py": {
        # p#tail-2, p#tail-0
        "test_shadow_package_thread_registers_its_real_message_body",
    },
    "test_render_semantic_selection.py": {
        # button.lf-shortcut-more
        "test_a_passage_still_offers_suggest_when_the_layer_has_no_reactions",
        # span.lf-shortcut, button.lf-shortcut-more
        "test_scrolling_target_hints_does_not_measure_hidden_targets",
        # button.lf-shortcut-more
        "test_short_inline_code_selection_offers_comment",
    },
    "test_render_startup.py": {
        # p#latency-line
        "test_a_captured_source_stays_pointable_and_pinned",
        # button.lf-shortcut-more
        "test_a_key_pressed_before_presentation_runs_once_the_page_presents",
        # button.inspect.lf-ui
        "test_a_projected_external_link_gets_the_pages_link_treatment",
        # span.lf-msg-sending, span.lf-thread-trailing
        "test_a_stale_response_cannot_rewind_timestamp_aging",
        # details.lf-thread-compact.lf-thread, span.lf-thread-topic
        "test_a_thread_says_what_the_agent_is_doing_about_it",
        # div.lf-banner-actions
        "test_opt_in_page_interface_joins_initial_widget_settlement",
        # div#outer-body, section#preview-host
        "test_reading_regions_read_posture_from_the_stylesheet_and_announce_a_shift",
        # span.lf-msg-sending, span.lf-thread-trailing
        "test_thread_timestamps_age_without_new_state",
        # leaf-margin-cluster.lf-ui.lf-margin-cluster
        "test_user_overrides_identify_state_that_differs_from_authored_inputs",
    },
    "test_render_threads.py": {
        # p in main.layout-column
        "test_a_reply_box_whose_thread_leaves_the_diff_takes_the_user_to_its_card",
        # div.lf-page-thread-msg.lf-ui.agent, div.lf-page-thread-msg.lf-ui.user
        "test_a_thread_resolved_while_its_reply_is_written_keeps_the_user_on_it",
        # div.lf-compose-field, a node since removed
        "test_a_turn_arriving_leaves_a_user_who_scrolled_away_from_their_box_reading",
        # div.lf-ui.lf-visual-mark.lf-target-paint.lf-visual-mark-here
        "test_an_agent_turn_arriving_holds_still_the_page_box_being_typed_in",
        # http://127.0.0.1:40119/versions/v1.html: a node since removed
        "test_two_standard_thread_lists_share_updates_but_not_local_state",
    },
    "test_render_visual_review_journey.py": {
        # h3.lf-vr-case-title
        "test_a_visual_review_states_where_its_pair_differs_in_every_view",
        # h3.lf-vr-case-title
        "test_embedded_visual_review_uses_native_scroll_chaining",
    },
    "test_render_widgets.py": {
        # button.lf-shortcut-more
        "test_a_board_says_which_column_each_card_is_in",
        # button.lf-shortcut-more, span.lf-shortcut
        "test_a_comment_on_a_wrapped_diff_line_names_the_line_an_unwrapped_one_names",
        # lf-board#feeders, p#insert
        "test_a_decision_travels_between_tabs_and_the_log_has_the_last_word",
        # button.lf-shortcut-more, span.lf-shortcut
        "test_a_diff_row_fills_to_the_end_of_its_line_and_to_the_end_of_a_narrow_box",
        # lf-sample#tone-sample
        "test_a_playground_dresses_each_sample_child_and_never_its_own_page",
        # leaf-margin-cluster.lf-ui.lf-margin-cluster
        "test_a_playground_sends_one_choice_while_the_first_press_is_in_flight",
        # lf-board#feeders, p#insert
        "test_a_pointer_decision_announces_without_needing_button_focus",
        # lf-sample#ring-sample, button#preview-button
        "test_a_pointer_press_on_a_playground_control_leaves_the_user_in_the_preview",
        # lf-swipe-pile#session-pass, lf-swipe-pile#session-keep
        "test_a_quoted_swipe_deck_is_a_static_labeled_exhibit",
        # button.lf-shortcut-more
        "test_a_side_list_is_a_queue_beside_the_item_it_opens",
        # lf-swipe-deck#session-triage, p in lf-ask#session-triage-decision
        "test_a_swipe_deck_reflows_with_its_parent_allocation",
        # button.lf-shortcut-more
        "test_a_table_of_contents_can_stop_at_an_authored_heading_level",
        # lf-command#cd-command, leaf-margin-cluster.lf-ui.lf-margin-cluster
        "test_a_thread_seated_in_a_widget_is_not_a_change_to_the_document",
        # button.lf-shortcut-more
        "test_an_ambiguous_decision_stays_one_gesture_while_retrying",
        # button.lf-shortcut-more
        "test_an_excerpt_shows_and_answers_to_its_source_line_numbers",
        # p#after
        "test_ask_action_name_functions_must_return_text",
        # leaf-margin-cluster.lf-ui.lf-margin-cluster
        "test_live_widget_subscription_releases_and_reconnects",
        # lf-ask#lp-rollback-region, p#lp-hold-policy
        "test_monitoring_evidence_moves_without_stealing_position_or_the_summary",
        # main.layout-column
        "test_notification_configuration_becomes_a_commentable_local_artifact",
        # lf-swipe-pile#session-pass, div.lf-swipe-controls.lf-ui
        "test_swipe_deck_activation_restores_a_standing_swipe_without_motion",
        # lf-swipe-pile#session-pass, div.lf-swipe-controls.lf-ui
        "test_swipe_deck_projects_the_same_exit_motion_as_a_local_swipe",
        # p#target-lifecycle-targeting-status.lf-targeting-status.lf-ui
        "test_targeting_controller_keeps_unresolved_targets_visible_and_blocks_submit",
        # main.layout-column
        "test_the_page_says_a_change_is_only_proposed",
    },
    "test_site.py": {
        # button.lf-shortcut-more, span.lf-shortcut
        "test_a_contained_replay_leaves_the_page_around_it_standing@site",
        # span.lf-shortcut, button.lf-shortcut-more
        "test_a_failed_gallery_frame_does_not_block_other_demos@site",
        # aside#triage-status, lf-column#col-repro
        "test_a_probe_in_flight_leaves_a_page_that_started_alone@site",
        # li in ol in div.lf-toc-rows
        "test_every_product_route_is_a_live_leaf_page@site",
        # h3.lf-vr-case-title, div.lf-vr-shot-host
        "test_every_published_page_stands_as_a_live_page@site",
        # button.lf-shortcut-more
        "test_interaction_gallery_contains_page_chrome@site",
        # div.lf-banner-actions, button.lf-shortcut-more
        "test_interaction_gallery_waits_for_a_restored_frame_tab@site",
        # li in ol in div.lf-toc-rows
        "test_published_product_page_renders",
        # h3.lf-vr-case-title, div.lf-vr-shot-host
        "test_published_visual_evidence_loads_from_its_page@site",
        # p#bg-motion-accept-copy
        "test_reduced_motion_leaves_gallery_play_explicit@site",
        # main.layout-column, div.lf-banner-actions
        "test_the_interaction_gallery_drives_real_widgets@site",
        # div.lf-banner-actions
        "test_the_interaction_gallery_reads_where_it_is_now@site",
    },
}

KNOWN_CARRIES = {
    "test_render_aim.py": {
        "test_a_side_comment_grows_down_from_the_line_it_was_opened_on": (
            "typing in leaf-text.lf-ui.lf-response-control.lf-fab-input moved div.lf-ui.lf-fab-bar.lf-target-paint"
        ),
        "test_an_above_comment_rechooses_after_vertical_target_motion": (
            "typing in leaf-text.lf-ui.lf-response-control.lf-fab-input moved div.lf-ui.lf-fab-bar.lf-target-paint"
        ),
        "test_the_catalog_sidenote_can_be_aimed_whole": (
            "typing in leaf-text.lf-ui.lf-response-control.lf-fab-input moved div.lf-ui.lf-fab-bar.lf-target-paint"
        ),
    },
}


def watches_shifts(test):
    """Whether a pytest node `test`'s pages watch for shifts at all.

    The nightly-marked tests do not yet. Linux CI finds shifts in them that a run here
    does not, as a margin cluster arriving after presentation, so the lists above hold
    what they do only as far as a survey reached, and a nightly run would fail on the
    rest. Most are the upgrade that the page before presentation carries
    (`shift_watch.js`); once that is fixed, they watch again."""
    return test.get_closest_marker("nightly") is None


def known_reports(test):
    """The shift reports a test's entries keep, for a pytest node `test`."""
    file, name = test.path.name, test.originalname
    unasked = (" moved without input",) if name in KNOWN_UNASKED.get(file, ()) else ()
    carried = KNOWN_CARRIES.get(file, {}).get(name)
    return unasked + ((carried,) if carried else ())
