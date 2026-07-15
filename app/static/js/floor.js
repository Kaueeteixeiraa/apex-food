(function () {
    const state = window.APEX_FLOOR;
    if (!state) return;

    const canvas = document.querySelector("[data-floor-canvas]");
    const tabs = document.querySelector("[data-area-tabs]");
    const panel = document.querySelector("[data-table-panel]");
    const panelTitle = document.querySelector("[data-panel-title]");
    const tableForm = document.querySelector("[data-table-form]");
    const tableOrders = document.querySelector("[data-table-orders]");
    const areaSelect = document.querySelector("[data-area-select]");
    const gridToggle = document.querySelector("[data-toggle-grid]");
    const closePanelButton = document.querySelector("[data-close-panel]");
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || "";
    const money = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

    let activeAreaId = state.areas[0]?.id || null;
    let selectedTableId = null;
    let zoom = 1;
    let pan = { x: 0, y: 0 };
    let panning = null;

    function applyViewport() {
        canvas.style.transform = `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`;
        canvas.style.transformOrigin = "0 0";
    }

    function fitMap() {
        const stage = canvas.parentElement;
        if (!stage) return;
        const scaleX = (stage.clientWidth - 24) / Math.max(canvas.scrollWidth || 820, 820);
        const scaleY = (stage.clientHeight - 64) / Math.max(canvas.scrollHeight || 620, 620);
        zoom = Math.min(1, Math.max(0.55, Math.min(scaleX, scaleY)));
        pan = { x: 12, y: 54 };
        applyViewport();
    }

    function slug(value) {
        return String(value || "")
            .normalize("NFD")
            .replace(/[\u0300-\u036f]/g, "")
            .toLowerCase()
            .replace(/[^a-z0-9]+/g, "-")
            .replace(/^-|-$/g, "");
    }

    function tableById(id) {
        return state.tables.find((table) => Number(table.id) === Number(id));
    }

    function updateUrl(id) {
        return state.updateUrlTemplate.replace(/0$/, String(id));
    }

    async function saveTable(tableId, fields) {
        const response = await fetch(updateUrl(tableId), {
            method: "PATCH",
            headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
            body: JSON.stringify(fields),
        });
        const result = await response.json();
        if (!response.ok || !result.ok) {
            throw new Error(result.error || "Não foi possível salvar a mesa.");
        }
        const index = state.tables.findIndex((table) => Number(table.id) === Number(tableId));
        if (index >= 0) {
            state.tables[index] = result.table;
        }
        render();
        if (selectedTableId) {
            selectTable(selectedTableId);
        }
    }

    function renderTabs() {
        tabs.innerHTML = state.areas.map((area) => `
            <button class="area-tab ${Number(area.id) === Number(activeAreaId) ? "active" : ""}" data-area-id="${area.id}" type="button">
                ${area.name}
            </button>
        `).join("");
        tabs.querySelectorAll("[data-area-id]").forEach((button) => {
            button.addEventListener("click", () => {
                activeAreaId = Number(button.dataset.areaId);
                if (areaSelect) areaSelect.value = activeAreaId;
                selectedTableId = null;
                panel.classList.remove("open");
                render();
            });
        });
    }

    function renderTables() {
        canvas.innerHTML = "";
        state.tables
            .filter((table) => Number(table.area_id) === Number(activeAreaId))
            .forEach((table) => {
                const element = document.createElement("button");
                element.type = "button";
                element.className = `floor-table shape-${table.shape} status-bg-${slug(table.status)}`;
                element.dataset.tableId = table.id;
                element.style.left = `${table.x}px`;
                element.style.top = `${table.y}px`;
                element.style.width = `${table.width}px`;
                element.style.height = `${table.height}px`;
                element.innerHTML = `
                    <strong>${table.name}</strong>
                    <small>${table.status}</small>
                    <span>${table.seats} lugares</span>
                    <i class="resize-handle"></i>
                `;
                attachDragBehavior(element, table);
                element.addEventListener("click", () => selectTable(table.id));
                canvas.appendChild(element);
            });
    }

    document.querySelectorAll("[data-floor-zoom]").forEach((button) => {
        button.addEventListener("click", () => {
            const action = button.dataset.floorZoom;
            if (action === "in") zoom = Math.min(1.6, zoom + 0.1);
            if (action === "out") zoom = Math.max(0.55, zoom - 0.1);
            if (action === "center") pan = { x: 12, y: 54 };
            if (action === "fit") fitMap();
            else applyViewport();
        });
    });

    canvas.parentElement?.addEventListener("pointerdown", (event) => {
        if (event.target !== canvas) return;
        panning = { id: event.pointerId, x: event.clientX, y: event.clientY, panX: pan.x, panY: pan.y };
        canvas.parentElement.setPointerCapture(event.pointerId);
    });
    canvas.parentElement?.addEventListener("pointermove", (event) => {
        if (!panning || panning.id !== event.pointerId) return;
        pan = { x: panning.panX + event.clientX - panning.x, y: panning.panY + event.clientY - panning.y };
        applyViewport();
    });
    canvas.parentElement?.addEventListener("pointerup", (event) => {
        if (panning?.id === event.pointerId) panning = null;
    });

    function attachDragBehavior(element, table) {
        let start = null;
        let moved = false;

        element.addEventListener("pointerdown", (event) => {
            if (event.button !== 0) return;
            moved = false;
            const resizing = event.target.classList.contains("resize-handle");
            start = {
                resizing,
                pointerX: event.clientX,
                pointerY: event.clientY,
                x: Number(table.x),
                y: Number(table.y),
                width: Number(table.width),
                height: Number(table.height),
            };
            element.setPointerCapture(event.pointerId);
        });

        element.addEventListener("pointermove", (event) => {
            if (!start) return;
            const dx = (event.clientX - start.pointerX) / zoom;
            const dy = (event.clientY - start.pointerY) / zoom;
            if (Math.abs(dx) + Math.abs(dy) > 2) moved = true;

            if (start.resizing) {
                table.width = Math.max(78, start.width + dx);
                table.height = Math.max(78, start.height + dy);
                element.style.width = `${table.width}px`;
                element.style.height = `${table.height}px`;
            } else {
                table.x = Math.max(0, start.x + dx);
                table.y = Math.max(0, start.y + dy);
                element.style.left = `${table.x}px`;
                element.style.top = `${table.y}px`;
            }
        });

        element.addEventListener("pointerup", async (event) => {
            if (!start) return;
            element.releasePointerCapture(event.pointerId);
            const fields = start.resizing
                ? { width: table.width, height: table.height }
                : { x: table.x, y: table.y };
            start = null;
            if (moved) {
                event.preventDefault();
                await saveTable(table.id, fields);
            }
        });
    }

    function renderOrders(tableId) {
        const orders = state.openOrders.filter((order) => Number(order.table_id) === Number(tableId));
        if (!orders.length) {
            tableOrders.innerHTML = '<p class="empty small">Nenhum pedido vinculado.</p>';
            return;
        }
        tableOrders.innerHTML = orders.map((order) => `
            <div class="linked-order">
                <strong>#${order.id} ${order.customer_name || ""}</strong>
                <span>${order.items_summary || "Sem itens"} · ${money.format(order.total || 0)}</span>
            </div>
        `).join("");
    }

    function selectTable(id) {
        selectedTableId = Number(id);
        const table = tableById(id);
        if (!table) return;
        const fields = tableForm.elements;

        panel.classList.add("open");
        panelTitle.textContent = table.name;
        fields.name.value = table.name || "";
        fields.status.value = table.status || "Livre";
        fields.seats.value = table.seats || 4;
        fields.customer_name.value = table.customer_name || "";
        fields.total.value = table.total || 0;
        if (fields.area_id) fields.area_id.value = table.area_id;
        renderOrders(id);
    }

    function render() {
        renderTabs();
        renderTables();
    }

    tableForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        if (!selectedTableId) return;
        const fields = tableForm.elements;
        await saveTable(selectedTableId, {
            name: fields.name.value,
            status: fields.status.value,
            seats: fields.seats.value,
            customer_name: fields.customer_name.value,
            total: fields.total.value,
            area_id: fields.area_id ? fields.area_id.value : undefined,
        });
        const table = tableById(selectedTableId);
        activeAreaId = Number(table.area_id);
        if (areaSelect) areaSelect.value = activeAreaId;
        render();
    });

    document.querySelectorAll("[data-quick-status]").forEach((button) => {
        button.addEventListener("click", async () => {
            if (!selectedTableId) return;
            await saveTable(selectedTableId, { status: button.dataset.quickStatus });
        });
    });

    document.querySelector("[data-close-table]").addEventListener("click", async () => {
        if (!selectedTableId) return;
        await saveTable(selectedTableId, { status: "Livre", customer_name: "", total: 0 });
    });

    closePanelButton.addEventListener("click", () => panel.classList.remove("open"));
    gridToggle.addEventListener("click", () => canvas.classList.toggle("grid-on"));

    if (areaSelect && activeAreaId) areaSelect.value = activeAreaId;
    render();
    fitMap();
})();
