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

    const posScreen = document.querySelector("[data-pos-screen]");
    if (posScreen) {
        const products = [...document.querySelectorAll("[data-product-card]")].map((card) => ({
            id: Number(card.dataset.addProduct),
            name: card.dataset.name,
            category: card.dataset.category,
            price: Number(card.dataset.price || 0),
            prep: Number(card.dataset.prep || 0),
            available: card.dataset.available === "1",
            description: card.dataset.description || "",
            image: card.dataset.image || "",
        }));
        const cart = new Map();
        const cartList = document.querySelector("[data-cart-list]");
        const cartJson = document.querySelector("[data-cart-json]");
        const cartCount = document.querySelector("[data-cart-count]");
        const subtotalTarget = document.querySelector("[data-subtotal]");
        const totalTarget = document.querySelector("[data-total]");
        const changeTarget = document.querySelector("[data-change]");
        const paymentInput = document.querySelector("[data-payment-input]");
        const selectedPayment = document.querySelector("[data-selected-payment]");
        const tableInput = document.querySelector("[data-table-input]");
        const productCount = document.querySelector("[data-product-count]");
        const search = document.querySelector("[data-pos-search]");
        const success = document.querySelector("[data-pos-success]");
        const favoritesPanel = document.querySelector("[data-favorites-panel]");
        const tableModal = document.querySelector("[data-table-modal]");
        const selectedTable = document.querySelector("[data-selected-table]");
        let activeCategory = "Todos";

        const escapeHtml = (value) => String(value || "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
        const getMoneyInput = (name) => Number(document.querySelector(`[name="${name}"]`)?.value || 0);
        const syncClock = () => {
            const now = new Date();
            const date = new Intl.DateTimeFormat("pt-BR").format(now);
            const time = new Intl.DateTimeFormat("pt-BR", { hour: "2-digit", minute: "2-digit" }).format(now);
            const dateTarget = document.querySelector("[data-pos-date]");
            const timeTarget = document.querySelector("[data-pos-time]");
            if (dateTarget) dateTarget.textContent = date;
            if (timeTarget) timeTarget.textContent = time;
        };

        const productById = (id) => products.find((product) => product.id === Number(id));
        const cartArray = () => [...cart.values()].map((item) => ({
            id: item.id,
            name: item.name,
            quantity: item.quantity,
            note: item.note || "",
        }));
        const totals = () => {
            const subtotal = [...cart.values()].reduce((sum, item) => sum + item.price * item.quantity, 0);
            const discount = getMoneyInput("discount");
            const serviceFee = getMoneyInput("service_fee");
            const deliveryFee = getMoneyInput("delivery_fee");
            const received = getMoneyInput("received_amount");
            const total = Math.max(subtotal - discount + serviceFee + deliveryFee, 0);
            return { subtotal, total, received, change: Math.max(received - total, 0) };
        };

        const renderCart = () => {
            const items = cartArray();
            if (!items.length) {
                cartList.innerHTML = `
                    <div class="pos-cart-empty">
                        <strong>Nenhum produto adicionado</strong>
                        <span>Toque em um produto para iniciar a venda.</span>
                    </div>
                `;
            } else {
                cartList.innerHTML = [...cart.values()].map((item) => `
                    <article class="pos-cart-item" data-cart-item="${item.id}">
                        <span class="cart-thumb"><img src="${escapeHtml(item.image)}" alt=""></span>
                        <div class="cart-main">
                            <strong>${escapeHtml(item.name)}</strong>
                            <input data-note="${item.id}" placeholder="Observação" value="${escapeHtml(item.note || "")}">
                        </div>
                        <div class="cart-qty">
                            <button type="button" data-dec="${item.id}">-</button>
                            <span>${item.quantity}</span>
                            <button type="button" data-inc="${item.id}">+</button>
                        </div>
                        <strong>${money.format(item.price * item.quantity)}</strong>
                        <button class="cart-remove" type="button" data-remove="${item.id}">×</button>
                    </article>
                `).join("");
            }

            const computed = totals();
            subtotalTarget.textContent = money.format(computed.subtotal);
            totalTarget.textContent = money.format(computed.total);
            changeTarget.textContent = money.format(computed.change);
            cartJson.value = JSON.stringify(items);
            cartCount.textContent = `${items.reduce((sum, item) => sum + item.quantity, 0)} itens`;
        };

        const addProduct = (id) => {
            const product = productById(id);
            if (!product || !product.available) return;
            const current = cart.get(product.id);
            cart.set(product.id, {
                ...product,
                quantity: current ? current.quantity + 1 : 1,
                note: current?.note || "",
            });
            const card = document.querySelector(`[data-add-product="${product.id}"]`);
            card?.classList.add("added");
            setTimeout(() => card?.classList.remove("added"), 280);
            renderCart();
        };

        const filterProducts = () => {
            const term = (search?.value || "").trim().toLowerCase();
            let visible = 0;
            document.querySelectorAll("[data-product-card]").forEach((card) => {
                const matchesCategory = activeCategory === "Todos" || card.dataset.category === activeCategory;
                const haystack = `${card.dataset.name} ${card.dataset.category} ${card.dataset.price}`.toLowerCase();
                const matchesSearch = !term || haystack.includes(term);
                const show = matchesCategory && matchesSearch;
                card.hidden = !show;
                if (show) visible += 1;
            });
            if (productCount) productCount.textContent = visible;
        };

        document.addEventListener("click", (event) => {
            const add = event.target.closest("[data-add-product]");
            if (add) addProduct(add.dataset.addProduct);

            const inc = event.target.closest("[data-inc]");
            if (inc) {
                const item = cart.get(Number(inc.dataset.inc));
                if (item) item.quantity += 1;
                renderCart();
            }

            const dec = event.target.closest("[data-dec]");
            if (dec) {
                const id = Number(dec.dataset.dec);
                const item = cart.get(id);
                if (item && item.quantity > 1) item.quantity -= 1;
                else cart.delete(id);
                renderCart();
            }

            const remove = event.target.closest("[data-remove]");
            if (remove) {
                cart.delete(Number(remove.dataset.remove));
                renderCart();
            }

            const category = event.target.closest("[data-category-filter]");
            if (category) {
                activeCategory = category.dataset.categoryFilter;
                document.querySelectorAll("[data-category-filter]").forEach((chip) => chip.classList.toggle("active", chip === category));
                filterProducts();
            }

            const payment = event.target.closest("[data-payment]");
            if (payment) {
                const method = payment.dataset.payment;
                document.querySelectorAll("[data-payment]").forEach((button) => button.classList.toggle("active", button === payment));
                document.querySelectorAll("[data-payment-detail]").forEach((detail) => detail.classList.toggle("active", detail.dataset.paymentDetail === method));
                paymentInput.value = method;
                selectedPayment.textContent = method;
            }

            const table = event.target.closest("[data-table-id]");
            if (table) {
                document.querySelectorAll("[data-table-id]").forEach((button) => button.classList.toggle("selected", button === table));
                tableInput.value = table.dataset.tableId;
                document.querySelector('[name="fulfillment_type"]').value = "Mesa";
                selectedTable.textContent = table.dataset.tableName;
                tableModal.hidden = true;
            }

            if (event.target.closest("[data-favorites-toggle]")) favoritesPanel.hidden = false;
            if (event.target.closest("[data-table-modal-open]")) tableModal.hidden = false;
            if (event.target.closest("[data-close-panel]")) event.target.closest(".pos-modal").hidden = true;
            if (event.target.classList.contains("pos-modal")) event.target.hidden = true;

            if (event.target.closest("[data-clear-cart]") || event.target.closest("[data-cancel-order]")) {
                cart.clear();
                renderCart();
            }
            if (event.target.closest("[data-clear-search]")) {
                search.value = "";
                filterProducts();
            }
            if (event.target.closest("[data-confirm-payment]")) {
                event.target.closest("[data-confirm-payment]").textContent = "Confirmado";
            }
        });

        document.addEventListener("input", (event) => {
            if (event.target.matches("[data-money-input]")) renderCart();
            if (event.target.matches("[data-pos-search]")) filterProducts();
            if (event.target.matches("[data-note]")) {
                const item = cart.get(Number(event.target.dataset.note));
                if (item) item.note = event.target.value;
                cartJson.value = JSON.stringify(cartArray());
            }
        });

        document.querySelector("[data-pos-checkout]")?.addEventListener("submit", (event) => {
            if (!cart.size) {
                event.preventDefault();
                cartList.classList.add("shake");
                setTimeout(() => cartList.classList.remove("shake"), 320);
                return;
            }
            success.classList.add("show");
            setTimeout(() => success.classList.remove("show"), 1800);
        });

        syncClock();
        setInterval(syncClock, 30000);
        filterProducts();
        renderCart();
    }
})();
