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
