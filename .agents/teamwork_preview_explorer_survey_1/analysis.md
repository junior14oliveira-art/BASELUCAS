# Static Analysis Report: Python f-string Escaping in `web_ui.py`

**Target File**: `apps/api/src/presentation/routers/web_ui.py`  
**Analyzer**: `teamwork_preview_explorer_survey_1`  
**Date**: 2026-08-10  

---

## 1. Executive Summary

A comprehensive static analysis of `apps/api/src/presentation/routers/web_ui.py` was performed to identify Python f-string interpolation syntax errors resulting from unescaped JavaScript template literal curly braces (`{` and `}`).

Inside Python multiline f-strings (`f"""..."""`), single curly braces `{...}` trigger Python runtime expression evaluation. When JavaScript template literals (such as `${variable}`) or JS expressions use single braces instead of double braces (`${{variable}}`), Python attempts to evaluate the JavaScript variable as a Python variable at HTTP request time in FastAPI.

This analysis identified **20 distinct syntax defects across 2 functions**:
1. **`renderCategorizedSidebar()`** (17 unescaped/malformed brace occurrences across 8 lines: lines 714, 715, 725, 726, 735, 737, 748, 749).
2. **`downloadExcel()`** (3 unescaped brace occurrences across 3 lines: lines 841, 844, 846).

These defects cause:
- **HTTP 500 Server Errors** when accessing `/app` or `/dashboard-ui` (Python raises `NameError` trying to resolve JS scope variables like `active`, `REAL_ORDERS`, `stObj`, `group`, `cnt`, `o`).
- **Missing Status IDs in UI**: Queue badges fail to show status IDs (e.g., `[3] Notebook - Geral`), rendering as literal text `[{stObj.id}]` or breaking script execution.
- **Excel Download Failure**: Clicking "Baixar Excel" fails due to `NameError: name 'o' is not defined` when building CSV rows.

---

## 2. Detailed Breakdown of Defective Code & Recommended Fixes

### A. Defects in `renderCategorizedSidebar()` (Lines 693–755)

#### 1. Lines 714–715 (Special 'Todos os pedidos' Group Item)
- **Line 714**:
  - *Original*: `<div class="status-tree-item ${active}" onclick="filterByStatus('Todos os pedidos', this)">`
  - *Defect*: `${active}` has single `{` and `}`. Python tries to evaluate Python variable `active` (not in scope).
  - *Fix*: `<div class="status-tree-item ${{active}}" onclick="filterByStatus('Todos os pedidos', this)">`

- **Line 715**:
  - *Original*: `<span>Todos os pedidos</span> <span class="status-badge-count" style="background:#0066FF;">${REAL_ORDERS.length}</span>`
  - *Defect*: `${REAL_ORDERS.length}` has single `{` and `}`. Python tries to evaluate `REAL_ORDERS.length` as a Python expression, causing `NameError` or `AttributeError`.
  - *Fix*: `<span>Todos os pedidos</span> <span class="status-badge-count" style="background:#0066FF;">${{REAL_ORDERS.length}}</span>`

#### 2. Lines 725–726 (Matched Status Group Items inside Loop)
- **Line 725**:
  - *Original*: `<div class="status-tree-item ${active}" onclick="filterByStatus('${stObj.name}', this)">`
  - *Defect*: `${active}` and `${stObj.name}` use single braces.
  - *Fix*: `<div class="status-tree-item ${{active}}" onclick="filterByStatus('${{stObj.name}}', this)">`

- **Line 726**:
  - *Original*: `<span><strong style="color:#0066FF;">[{stObj.id}]</strong> {stObj.name}</span> <span class="status-badge-count" style="background:${stObj.color || '#64748B'};">${cnt}</span>`
  - *Defect*:
    1. `[{stObj.id}]` is missing the `$` prefix AND uses single braces `{stObj.id}`. It fails Python evaluation and fails JS template interpolation.
    2. `{stObj.name}` is missing the `$` prefix AND uses single braces `{stObj.name}`.
    3. `${stObj.color || '#64748B'}` uses single braces and contains JS logical OR (`||`), causing a Python `SyntaxError`.
    4. `${cnt}` uses single braces, triggering Python `NameError: name 'cnt' is not defined`.
  - *Fix*: `<span><strong style="color:#0066FF;">[${{stObj.id}}]</strong> ${{stObj.name}}</span> <span class="status-badge-count" style="background:${{stObj.color || '#64748B'}};">${{cnt}}</span>`

#### 3. Lines 735 & 737 (Group Header and Items Append)
- **Line 735**:
  - *Original*: `<span>${group.name}</span> <span>${groupTotal}</span>`
  - *Defect*: `${group.name}` and `${groupTotal}` use single braces.
  - *Fix*: `<span>${{group.name}}</span> <span>${{groupTotal}}</span>`

- **Line 737**:
  - *Original*: `${groupItemsHtml}`;
  - *Defect*: `${groupItemsHtml}` uses single braces.
  - *Fix*: `${{groupItemsHtml}}`;

#### 4. Lines 748–749 (Remaining 'OUTRAS FILAS' Group Items)
- **Line 748**:
  - *Original*: `<div class="status-tree-item ${active}" onclick="filterByStatus('${stObj.name}', this)">`
  - *Defect*: `${active}` and `${stObj.name}` use single braces.
  - *Fix*: `<div class="status-tree-item ${{active}}" onclick="filterByStatus('${{stObj.name}}', this)">`

- **Line 749**:
  - *Original*: `<span><strong style="color:#0066FF;">[{stObj.id}]</strong> {stObj.name}</span> <span class="status-badge-count" style="background:${stObj.color || '#64748B'};">${cnt}</span>`
  - *Defect*:
    1. `[{stObj.id}]` missing `$` prefix and using single braces.
    2. `{stObj.name}` missing `$` prefix and using single braces.
    3. `${stObj.color || '#64748B'}` using single braces with JS `||`.
    4. `${cnt}` using single braces.
  - *Fix*: `<span><strong style="color:#0066FF;">[${{stObj.id}}]</strong> ${{stObj.name}}</span> <span class="status-badge-count" style="background:${{stObj.color || '#64748B'}};">${{cnt}}</span>`

---

### B. Defects in `downloadExcel()` (Lines 833–860)

#### Lines 841, 844, 846 (CSV Row Building inside `filtered.forEach(o => ...)` Loop)
- **Line 841**:
  - *Original*: `` `"${o.customer}"`, ``
  - *Defect*: `{o.customer}` uses single braces. Python evaluates `o.customer` during f-string evaluation, raising `NameError: name 'o' is not defined`.
  - *Fix*: `` `"${{o.customer}}"`, ``

- **Line 844**:
  - *Original*: `` `"${o.status}"`, ``
  - *Defect*: `{o.status}` uses single braces, raising `NameError: name 'o' is not defined`.
  - *Fix*: `` `"${{o.status}}"`, ``

- **Line 846**:
  - *Original*: `` `"${o.date}"` ``
  - *Defect*: `{o.date}` uses single braces, raising `NameError: name 'o' is not defined`.
  - *Fix*: `` `"${{o.date}}"` ``

---

## 3. Function-by-Function Audit Table

| JS Function Name | Lines | Status | Details / Issues Found |
| :--- | :--- | :--- | :--- |
| `matchesSearch` | 552–556 | PASS | Escaped properly (`{{` and `}}`). |
| `getStatusColor` | 558–565 | PASS | Escaped properly (`{{` and `}}`). |
| `distribuicaoPorStatus` | 567–575 | PASS | Escaped properly (`{{` and `}}`). |
| `initCharts` | 577–632 | PASS | Escaped properly (`{{` and `}}`). |
| `renderOperatorsDropdown` | 634–639 | PASS | Escaped properly (`${{o.id}}`, `${{o.name}}`). |
| `switchOperator` | 641–647 | PASS | Escaped properly (`{{` and `}}`). |
| `renderOperatorsCrudList` | 649–662 | PASS | Escaped properly (`${{o.id}}`, `${{o.name}}`, `${{o.role}}`). |
| `createOperator` | 664–682 | PASS | Escaped properly (`{{` and `}}`). |
| `deleteOperator` | 684–691 | PASS | Escaped properly (`${{opId}}`, `{{ method: 'DELETE' }}`). |
| **`renderCategorizedSidebar`** | **693–755** | **FAIL** | **17 unescaped/missing `$` braces across lines 714, 715, 725, 726, 735, 737, 748, 749.** |
| `filterByStatus` | 757–763 | PASS | Escaped properly (`{{` and `}}`). |
| `applyFilters` | 765–789 | PASS | Escaped properly (`{{` and `}}`). |
| `renderOrdersTable` | 791–828 | PASS | Escaped properly (`${{...}}`). |
| **`downloadExcel`** | **833–860** | **FAIL** | **3 unescaped braces across lines 841, 844, 846.** |
| `renderProductsTable` | 862–888 | PASS | Escaped properly (`${{...}}`). |
| `openAlterFilaModal` | 890–894 | PASS | Escaped properly (`${{s.id}}`, `${{s.name}}`). |
| `closeAlterFilaModal` | 896–898 | PASS | Escaped properly (`{{` and `}}`). |
| `applyFilaChange` | 900–922 | PASS | Escaped properly (`${{stObj.name}}`, `${{stObj.id}}`). |
| `openOperatorModal` / `closeOperatorModal` | 924–929 | PASS | Escaped properly (`{{` and `}}`). |
| `switchTab` | 931–951 | PASS | Escaped properly (`{{` and `}}`). |
| `syncWithBaseLinkerAPI` | 953–956 | PASS | Escaped properly (`{{` and `}}`). |
| `filterGlobalData` | 958–962 | PASS | Escaped properly (`{{` and `}}`). |

---

## 4. Proposed Source Code Replacement Snippets

Below are the exact replacement chunks for `apps/api/src/presentation/routers/web_ui.py`:

### Replacement Chunk 1: `renderCategorizedSidebar()` (Lines 713–754)

```javascript
            groupItemsHtml += `
              <div class="status-tree-item ${{active}}" onclick="filterByStatus('Todos os pedidos', this)">
                <span>Todos os pedidos</span> <span class="status-badge-count" style="background:#0066FF;">${{REAL_ORDERS.length}}</span>
              </div>`;
          }} else {{
            const stObj = REAL_STATUSES.find(s => s.name.toLowerCase() === sName.toLowerCase());
            if (stObj) {{
              groupedSet.add(stObj.id);
              const cnt = counts[stObj.name] || 0;
              groupTotal += cnt;
              const active = activeStatusFilter === stObj.name ? 'active' : '';
              groupItemsHtml += `
                <div class="status-tree-item ${{active}}" onclick="filterByStatus('${{stObj.name}}', this)">
                  <span><strong style="color:#0066FF;">[${{stObj.id}}]</strong> ${{stObj.name}}</span> <span class="status-badge-count" style="background:${{stObj.color || '#64748B'}};">${{cnt}}</span>
                </div>`;
            }}
          }}
        }});

        if (groupItemsHtml) {{
          html += `
            <div class="status-group-header">
              <span>${{group.name}}</span> <span>${{groupTotal}}</span>
            </div>
            ${{groupItemsHtml}}`;
        }}
      }});

      const remaining = REAL_STATUSES.filter(s => !groupedSet.has(s.id));
      if (remaining.length > 0) {{
        html += `<div class="status-group-header">OUTRAS FILAS</div>`;
        remaining.forEach(stObj => {{
          const cnt = counts[stObj.name] || 0;
          const active = activeStatusFilter === stObj.name ? 'active' : '';
          html += `
            <div class="status-tree-item ${{active}}" onclick="filterByStatus('${{stObj.name}}', this)">
              <span><strong style="color:#0066FF;">[${{stObj.id}}]</strong> ${{stObj.name}}</span> <span class="status-badge-count" style="background:${{stObj.color || '#64748B'}};">${{cnt}}</span>
            </div>`;
        }});
      }}
```

### Replacement Chunk 2: `downloadExcel()` (Lines 838–849)

```javascript
      filtered.forEach(o => {{
        const row = [
          o.id,
          `"${{o.customer}}"`,
          `""`, // no email in this UI struct
          `""`, // no phone in this UI struct
          `"${{o.status}}"`,
          o.price,
          `"${{o.date}}"`
        ];
        csv += row.join(",") + "\n";
      }});
```

---

## 5. Verification Plan for Implementer Agent

1. **Syntax Verification**: Run `python -c "import ast; ast.parse(open('apps/api/src/presentation/routers/web_ui.py', encoding='utf-8').read())"` to confirm Python parses `web_ui.py` without syntax errors.
2. **Server Execution**: Launch API or endpoint `/app` / `/dashboard-ui` to verify HTTP status `200 OK` (no HTTP 500).
3. **Frontend Rendering**:
   - Inspect Left Sidebar: Verify all 8 status categories load correctly and status items display `[ID] Name` (e.g. `[3] Notebook - Geral`).
   - Click "Baixar Excel": Confirm `pedidos_baselucas.csv` is generated and downloaded without browser console errors.
