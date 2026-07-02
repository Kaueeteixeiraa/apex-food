(function () {
    const money = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

    document.querySelectorAll(".flash").forEach((flash) => {
        setTimeout(() => flash.classList.add("fade-out"), 4200);
    });

    const chart = document.querySelector("#salesChart");
    if (chart) {
        const data = JSON.parse(chart.dataset.chart || "[]");
        const max = Math.max(...data.map((item) => Number(item.total)), 1);
        chart.innerHTML = data.map((item) => {
            const height = Math.max((Number(item.total) / max) * 100, item.total > 0 ? 10 : 4);
            return `
                <div class="bar-item">
                    <div class="bar-track"><span style="height:${height}%"></span></div>
                    <small>${item.label}</small>
                    <strong>${money.format(item.total)}</strong>
                </div>
            `;
        }).join("");
    }

    const posForm = document.querySelector(".pos-form");
    if (posForm) {
        const totalTarget = posForm.querySelector("[data-pos-total]");
        const updateTotal = () => {
            const orderOption = posForm.order_id.selectedOptions[0];
            const productOption = posForm.product_id.selectedOptions[0];
            const quantity = Number(posForm.quantity.value || 1);
            const discount = Number(posForm.discount.value || 0);
            const serviceFee = Number(posForm.service_fee.value || 0);
            const subtotal = orderOption?.value
                ? Number(orderOption.dataset.total || 0)
                : Number(productOption?.dataset.price || 0) * quantity;
            const total = Math.max(subtotal - discount + serviceFee, 0);
            totalTarget.textContent = money.format(total);
        };

        posForm.querySelectorAll("select, input").forEach((field) => {
            field.addEventListener("input", updateTotal);
            field.addEventListener("change", updateTotal);
        });
        updateTotal();
    }
})();
