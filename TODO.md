# Librarian TODO

Bugs, issues, and improvements to address.

---

## Priority: High

- [ ] **Show warning message when running without config**
  - Currently silently uses defaults with empty watch directories
  - Should warn user: "No config file found. Using defaults. Run `librarian init` to configure."
  - Applies to: `serve` and `mcp serve` commands

---

## Priority: Medium

- [ ] **Web UI: Empty state improvements**
  - Show setup instructions when no documents exist
  - Link to upload page
  - Show "Configure watch directory" prompt if empty

- [ ] **CLI: `librarian init` should create config file**
  - Currently only shows config location
  - Should create default config with watch directory prompt

- [ ] **MCP: Better error messages**
  - Tool errors should be user-friendly, not stack traces
  - Include suggestion for common issues

---

## Priority: Low

- [ ] **Web UI: Dark mode**
  - Tailwind dark: variant support
  - Toggle in settings

- [ ] **Web UI: Keyboard shortcuts**
  - `/` to focus search
  - `?` to show help
  - `j/k` to navigate results

- [ ] **Search: Result highlighting**
  - Highlight matching terms in search results
  - Semantic matches show context

---

## Completed

- [x] M8: Web UI basic implementation
- [x] M7.5: OpenClaw skill
- [x] M7: MCP Server
- [x] M6.5: Service Layer Extraction
- [x] M1-M6: Core features

---

## Notes

- Move completed items to "Completed" section
- Add priority labels: High/Medium/Low
- Link to GitHub issues when created
