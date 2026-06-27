/* ============================================================
   Skeleton loaders - Utilidades para estados de carga
   ============================================================ */

const Skeletons = {
    /**
     * Crea un skeleton de tarjeta (para dashboards).
     * @param {number} count - Numero de tarjetas
     * @returns {string} HTML del skeleton
     */
    cards(count = 3) {
        let html = '<div class="grid grid-cols-1 md:grid-cols-3 gap-6">';
        for (let i = 0; i < count; i++) {
            html += `
                <div class="card-premium p-6">
                    <div class="skeleton h-8 w-8 rounded-lg mb-4"></div>
                    <div class="skeleton skeleton-text"></div>
                    <div class="skeleton skeleton-text"></div>
                </div>`;
        }
        html += '</div>';
        return html;
    },

    /**
     * Crea un skeleton de tabla.
     * @param {number} rows - Numero de filas
     * @returns {string} HTML del skeleton
     */
    table(rows = 5) {
        let html = '<div class="card-premium p-6">';
        for (let i = 0; i < rows; i++) {
            html += `
                <div class="flex items-center gap-4 py-3 border-b border-slate-100 last:border-0">
                    <div class="skeleton h-10 w-10 rounded-full"></div>
                    <div class="flex-1">
                        <div class="skeleton skeleton-text"></div>
                        <div class="skeleton skeleton-text" style="width:40%"></div>
                    </div>
                    <div class="skeleton h-6 w-20 rounded-full"></div>
                </div>`;
        }
        html += '</div>';
        return html;
    },

    /**
     * Crea un skeleton de lista simple.
     * @param {number} items - Numero de items
     * @returns {string} HTML del skeleton
     */
    list(items = 4) {
        let html = '';
        for (let i = 0; i < items; i++) {
            html += `
                <div class="flex items-center gap-3 py-3">
                    <div class="skeleton h-12 w-12 rounded-xl"></div>
                    <div class="flex-1">
                        <div class="skeleton skeleton-text"></div>
                        <div class="skeleton skeleton-text" style="width:50%"></div>
                    </div>
                </div>`;
        }
        return html;
    },

    /**
     * Muestra un skeleton dentro de un elemento.
     * @param {HTMLElement} el - Elemento contenedor
     * @param {string} html - HTML del skeleton
     */
    show(el, html) {
        if (el) el.innerHTML = html;
    },

    /**
     * Limpia un elemento.
     * @param {HTMLElement} el
     */
    clear(el) {
        if (el) el.innerHTML = '';
    },
};
