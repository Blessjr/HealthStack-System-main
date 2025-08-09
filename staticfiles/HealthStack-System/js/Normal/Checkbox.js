document.addEventListener('DOMContentLoaded', () => {
    const masterCheckbox = document.querySelector('#select-all');
    const checkboxes = document.querySelectorAll('.checkbox-item');

    if (masterCheckbox && checkboxes.length > 0) {
        masterCheckbox.addEventListener('change', () => {
            const isChecked = masterCheckbox.checked;
            checkboxes.forEach(checkbox => {
                checkbox.checked = isChecked;
                toggleRowHighlight(checkbox);
            });
        });

        checkboxes.forEach(checkbox => {
            checkbox.addEventListener('change', () => {
                toggleRowHighlight(checkbox);

                // Update master checkbox state
                const allChecked = [...checkboxes].every(cb => cb.checked);
                masterCheckbox.checked = allChecked;
            });
        });
    }

    // Optional: highlight the row when checked
    function toggleRowHighlight(checkbox) {
        const row = checkbox.closest('tr') || checkbox.closest('.checkbox-row');
        if (row) {
            if (checkbox.checked) {
                row.classList.add('selected');
            } else {
                row.classList.remove('selected');
            }
        }
    }
});
