(function () {
    const money = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

    document.querySelectorAll(".flash").forEach((flash) => {
        setTimeout(() => flash.classList.add("fade-out"), 4200);
    });

    const loginForm = document.querySelector("[data-login-form]");
    if (loginForm) {
        const loader = document.querySelector("[data-auth-loader]");
        const loginButton = document.querySelector("[data-login-button]");
        let submitting = false;

        loginForm.addEventListener("submit", (event) => {
            if (submitting) return;
            event.preventDefault();

            if (!loginForm.checkValidity()) {
                loginForm.reportValidity();
                return;
            }

            submitting = true;
            loginButton.classList.add("loading");
            loginButton.textContent = "Validando acesso";
            loader?.classList.add("show");
            setTimeout(() => loginForm.submit(), 720);
        });
    }

    const registerForm = document.querySelector("[data-register-form]");
    if (registerForm) {
        const steps = [...registerForm.querySelectorAll("[data-step]")];
        const progress = [...document.querySelectorAll("[data-register-progress] .progress-step")];
        const prev = registerForm.querySelector("[data-prev-step]");
        const next = registerForm.querySelector("[data-next-step]");
        const submit = registerForm.querySelector("[data-submit-step]");
        let current = 0;

        const fieldsInStep = (step) => [...steps[step].querySelectorAll("input, select, textarea")];
        const validateStep = () => {
            const invalid = fieldsInStep(current).find((field) => !field.checkValidity());
            if (invalid) {
                invalid.reportValidity();
                return false;
            }
            return true;
        };
        const renderStep = () => {
            steps.forEach((step, index) => step.classList.toggle("active", index === current));
            progress.forEach((step, index) => step.classList.toggle("active", index <= current));
            prev.hidden = current === 0;
            next.hidden = current === steps.length - 1;
            submit.hidden = current !== steps.length - 1;
        };

        prev.addEventListener("click", () => {
            current = Math.max(current - 1, 0);
            renderStep();
        });
        next.addEventListener("click", () => {
            if (!validateStep()) return;
            current = Math.min(current + 1, steps.length - 1);
            renderStep();
        });
        registerForm.addEventListener("submit", (event) => {
            if (![0, 1, 2].every((step) => fieldsInStep(step).every((field) => field.checkValidity()))) {
                event.preventDefault();
                current = steps.findIndex((step) => fieldsInStep(Number(step.dataset.step)).some((field) => !field.checkValidity()));
                if (current < 0) current = 0;
                renderStep();
                validateStep();
            }
        });
        renderStep();
    }

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

    // Dashboard premium charts: SVG line, status bars and payment donut.
    const salesLineChart = document.querySelector("#salesLineChart");
    if (salesLineChart) {
        const data = JSON.parse(salesLineChart.dataset.chart || "[]");
        const width = 640;
        const height = 210;
        const padX = 34;
        const padY = 28;
        const max = Math.max(...data.map((item) => Number(item.total)), 1);
        const step = data.length > 1 ? (width - padX * 2) / (data.length - 1) : 0;
        const points = data.map((item, index) => {
            const x = padX + index * step;
            const y = height - padY - (Number(item.total) / max) * (height - padY * 2);
            return { ...item, x, y };
        });
        const line = points.map((point) => `${point.x},${point.y}`).join(" ");
        const area = `${padX},${height - padY} ${line} ${width - padX},${height - padY}`;

        salesLineChart.innerHTML = `
            <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Vendas dos ultimos 7 dias">
                <defs>
                    <linearGradient id="salesLine" x1="0" x2="1" y1="0" y2="0">
                        <stop offset="0%" stop-color="#7C3AED" />
                        <stop offset="52%" stop-color="#A855F7" />
                        <stop offset="100%" stop-color="#F59E0B" />
                    </linearGradient>
                    <linearGradient id="salesArea" x1="0" x2="0" y1="0" y2="1">
                        <stop offset="0%" stop-color="rgba(124,58,237,.34)" />
                        <stop offset="100%" stop-color="rgba(124,58,237,0)" />
                    </linearGradient>
                </defs>
                ${[0, 1, 2, 3].map((row) => {
                    const y = padY + row * ((height - padY * 2) / 3);
                    return `<line class="chart-grid-line" x1="${padX}" x2="${width - padX}" y1="${y}" y2="${y}" />`;
                }).join("")}
                <polygon class="line-chart-area" points="${area}" />
                <polyline class="line-chart-path" points="${line}" />
                ${points.map((point) => `
                    <g>
                        <circle class="line-chart-dot" cx="${point.x}" cy="${point.y}" r="4.5" />
                        <text class="line-chart-label" x="${point.x}" y="${height - 6}" text-anchor="middle">${point.label}</text>
                    </g>
                `).join("")}
            </svg>
        `;
    }

    const statusChart = document.querySelector("#statusChart");
    if (statusChart) {
        const data = JSON.parse(statusChart.dataset.chart || "[]");
        const max = Math.max(...data.map((item) => Number(item.value)), 1);
        statusChart.innerHTML = data.map((item) => {
            const width = Math.max((Number(item.value) / max) * 100, item.value > 0 ? 10 : 4);
            return `
                <div class="status-chart-row">
                    <div class="status-chart-top">
                        <span>${item.label}</span>
                        <strong>${item.value}</strong>
                    </div>
                    <div class="status-chart-track">
                        <i style="width:${width}%; background:${item.color}"></i>
                    </div>
                </div>
            `;
        }).join("");
    }

    const paymentChart = document.querySelector("#paymentChart");
    if (paymentChart) {
        const data = JSON.parse(paymentChart.dataset.chart || "[]");
        const total = data.reduce((sum, item) => sum + Number(item.value || 0), 0);
        const donut = paymentChart.querySelector("[data-payment-donut]");
        const legend = paymentChart.querySelector("[data-payment-legend]");
        let cursor = 0;
        const segments = data.map((item) => {
            const percent = total > 0 ? (Number(item.value || 0) / total) * 100 : 0;
            const start = cursor;
            cursor += percent;
            return `${item.color} ${start}% ${cursor}%`;
        });
        donut.style.background = total > 0
            ? `conic-gradient(${segments.join(", ")})`
            : "conic-gradient(rgba(255,255,255,.08) 0 100%)";
        donut.innerHTML = `<span>${money.format(total)}</span><small>Total</small>`;
        legend.innerHTML = data.map((item) => `
            <div class="payment-legend-item">
                <i style="background:${item.color}"></i>
                <span>${item.label}</span>
                <strong>${money.format(item.value || 0)}</strong>
            </div>
        `).join("");
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
