// Main JavaScript file for REMS

document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'))
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl)
    });

    // Initialize date inputs
    const dateInputs = document.querySelectorAll('input[type="date"]');
    dateInputs.forEach(input => {
        const today = new Date().toISOString().split('T')[0];
        input.min = today;
    });

    // Form validation
    const forms = document.querySelectorAll('.needs-validation');
    forms.forEach(form => {
        form.addEventListener('submit', event => {
            if (!form.checkValidity()) {
                event.preventDefault();
                event.stopPropagation();
            }
            form.classList.add('was-validated');
        });
    });

    // Dynamic rent calculation
    const rentDurationInputs = document.querySelectorAll('input[name="start_date"], input[name="end_date"]');
    const rentAmountDisplay = document.getElementById('rent-amount');
    const monthlyRate = rentAmountDisplay ? parseFloat(rentAmountDisplay.dataset.rate) : 0;

    rentDurationInputs.forEach(input => {
        input.addEventListener('change', () => {
            const startDate = new Date(document.querySelector('input[name="start_date"]').value);
            const endDate = new Date(document.querySelector('input[name="end_date"]').value);

            if (startDate && endDate && startDate < endDate) {
                const months = (endDate.getFullYear() - startDate.getFullYear()) * 12 + 
                             (endDate.getMonth() - startDate.getMonth());
                const totalAmount = months * monthlyRate;
                if (rentAmountDisplay) {
                    rentAmountDisplay.textContent = `$${totalAmount.toFixed(2)}`;
                }
            }
        });
    });

    // Image preview
    const imageInput = document.querySelector('input[type="file"][accept="image/*"]');
    const imagePreview = document.getElementById('image-preview');

    if (imageInput && imagePreview) {
        imageInput.addEventListener('change', event => {
            const file = event.target.files[0];
            if (file) {
                const reader = new FileReader();
                reader.onload = e => {
                    imagePreview.src = e.target.result;
                    imagePreview.style.display = 'block';
                };
                reader.readAsDataURL(file);
            }
        });
    }

    // Property filter
    const filterInputs = document.querySelectorAll('.property-filter input, .property-filter select');
    const propertyCards = document.querySelectorAll('.property-card');

    filterInputs.forEach(input => {
        input.addEventListener('change', filterProperties);
    });

    function filterProperties() {
        const filters = {
            minPrice: parseFloat(document.querySelector('input[name="min_price"]')?.value) || 0,
            maxPrice: parseFloat(document.querySelector('input[name="max_price"]')?.value) || Infinity,
            bedrooms: parseInt(document.querySelector('select[name="bedrooms"]')?.value) || 0,
            propertyType: document.querySelector('select[name="property_type"]')?.value || 'all'
        };

        propertyCards.forEach(card => {
            const price = parseFloat(card.dataset.price);
            const bedrooms = parseInt(card.dataset.bedrooms);
            const type = card.dataset.type;

            const matchesFilters = 
                price >= filters.minPrice &&
                price <= filters.maxPrice &&
                (filters.bedrooms === 0 || bedrooms === filters.bedrooms) &&
                (filters.propertyType === 'all' || type === filters.propertyType);

            card.style.display = matchesFilters ? 'block' : 'none';
        });
    }
});
