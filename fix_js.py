import re

with open('frontend/punti_consegna.html', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Remove the standalone event listener that causes the null error
content = re.sub(
    r'document\.getElementById\(\'pointsContainer\'\)\.addEventListener\(\'click\', function\(e\) \{[\s\S]*?\}\);\s*', 
    '', 
    content
)

# 2. Update the existing event delegation to handle the new button attributes
new_delegation = '''// Event Delegation for action buttons
            document.getElementById("listContainer").addEventListener("click", (e) => {
                const btn = e.target.closest(".btn-icon");
                if (!btn) return;
                
                const action = btn.getAttribute("data-action");
                const pointId = btn.getAttribute("data-point-id");
                
                if (action === "geo" && pointId) {
                    window.openMapModal(pointId);
                } else if (action === "edit" && pointId) {
                    window.openEditModal(pointId);
                }
            });'''
content = re.sub(
    r'// Event Delegation for action buttons[\s\S]*?\}\);',
    new_delegation,
    content
)

with open('frontend/punti_consegna.html', 'w', encoding='utf-8') as f:
    f.write(content)
print('Fixed event delegation')
