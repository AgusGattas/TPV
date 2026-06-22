/**
 * Impresión de tickets ESC/POS vía QZ Tray.
 */
window.TodoBrillaPrint = (function () {
    const STORAGE_KEY = "todobrilla_thermal_printer";
    let qzReady = false;
    let qzConfig = null;

    function getCsrfToken() {
        const input = document.querySelector("[name=csrfmiddlewaretoken]");
        if (input && input.value) {
            return input.value;
        }
        const match = document.cookie.match(/csrftoken=([^;]+)/);
        return match ? decodeURIComponent(match[1]) : "";
    }

    function initConfig(config) {
        qzConfig = config;
    }

    async function setupQzSecurity() {
        if (qzReady || !qzConfig) {
            return;
        }

        qz.security.setCertificatePromise(function (resolve, reject) {
            fetch(qzConfig.certUrl, { credentials: "same-origin", cache: "no-store" })
                .then(function (response) {
                    if (!response.ok) {
                        throw new Error("No se pudo cargar el certificado QZ");
                    }
                    return response.text();
                })
                .then(resolve)
                .catch(reject);
        });

        qz.security.setSignatureAlgorithm("SHA512");
        qz.security.setSignaturePromise(function (toSign) {
            return function (resolve, reject) {
                const signUrl =
                    qzConfig.signUrl +
                    (qzConfig.signUrl.indexOf("?") >= 0 ? "&" : "?") +
                    "request=" +
                    encodeURIComponent(toSign);

                fetch(signUrl, {
                    method: "GET",
                    credentials: "same-origin",
                    cache: "no-store",
                })
                    .then(function (response) {
                        if (!response.ok) {
                            return response.text().then(function (text) {
                                throw new Error(text || "No se pudo firmar la petición QZ");
                            });
                        }
                        return response.text();
                    })
                    .then(resolve)
                    .catch(function () {
                        fetch(qzConfig.signUrl, {
                            method: "POST",
                            credentials: "same-origin",
                            headers: {
                                "Content-Type": "application/json",
                                "X-CSRFToken": getCsrfToken(),
                            },
                            body: JSON.stringify({ request: toSign }),
                        })
                            .then(function (response) {
                                if (!response.ok) {
                                    return response.text().then(function (text) {
                                        throw new Error(text || "No se pudo firmar la petición QZ");
                                    });
                                }
                                return response.text();
                            })
                            .then(resolve)
                            .catch(reject);
                    });
            };
        });

        qzReady = true;
    }

    async function connect() {
        await setupQzSecurity();
        if (!qz.websocket.isActive()) {
            try {
                await qz.websocket.connect();
            } catch (error) {
                throw formatQzError(error);
            }
        }
    }

    function formatQzError(error) {
        const message = error && error.message ? error.message : String(error);
        if (/blocked by client/i.test(message)) {
            return new Error(
                "QZ Tray bloqueó esta conexión (probablemente pulsaste Block antes). " +
                "En Mac: QZ Tray > Advanced > Site Manager > Blocked, eliminá localhost. " +
                "O ejecutá: ./scripts/install_qz_tray_mac.sh"
            );
        }
        if (/unable to establish connection|connection refused|websocket/i.test(message)) {
            return new Error(
                "No se pudo conectar con QZ Tray. Verificá que QZ Tray esté abierto en esta Mac."
            );
        }
        return error instanceof Error ? error : new Error(message);
    }

    function buildTicketUrl(saleId) {
        return qzConfig.ticketUrlTemplate.replace("SALE_ID", String(saleId));
    }

    async function fetchTicketData(saleId) {
        const response = await fetch(buildTicketUrl(saleId), { credentials: "same-origin" });
        if (!response.ok) {
            throw new Error("No se pudo obtener el ticket");
        }
        return response.json();
    }

    async function listPrinters() {
        await connect();
        return qz.printers.find();
    }

    function guessThermalPrinter(printers) {
        return printers.find(function (name) {
            return /pos|thermal|ticket|tm-|epson|star|bixolon|xprinter|gprinter|citizen|bema|hasar/i.test(name);
        });
    }

    async function choosePrinter(printers) {
        const suggested = guessThermalPrinter(printers) || printers[0];
        const message =
            "Elegí la impresora térmica para tickets.\n\n" +
            printers.map(function (name, index) {
                return (index + 1) + ". " + name;
            }).join("\n") +
            "\n\nEscribí el nombre exacto:";

        const chosen = window.prompt(message, suggested);
        if (!chosen) {
            throw new Error("Impresión cancelada");
        }
        if (printers.indexOf(chosen) === -1) {
            throw new Error("Impresora no válida: " + chosen);
        }
        localStorage.setItem(STORAGE_KEY, chosen);
        return chosen;
    }

    async function getPrinterName(forceChoose) {
        if (!forceChoose) {
            const saved = localStorage.getItem(STORAGE_KEY);
            if (saved) {
                return saved;
            }
        }

        const printers = await listPrinters();
        if (!printers || printers.length === 0) {
            throw new Error("No se encontraron impresoras. Verificá que QZ Tray esté abierto.");
        }
        return choosePrinter(printers);
    }

    async function printSale(saleId, options) {
        options = options || {};
        await connect();
        const printerName = await getPrinterName(Boolean(options.forceChoose));
        const ticket = await fetchTicketData(saleId);
        const config = qz.configs.create(printerName);
        const data = [{
            type: "raw",
            format: "command",
            flavor: "base64",
            data: ticket.data,
        }];
        await qz.print(config, data);
        return printerName;
    }

    function setPrinter(name) {
        if (name) {
            localStorage.setItem(STORAGE_KEY, name);
        }
    }

    function getSavedPrinter() {
        return localStorage.getItem(STORAGE_KEY);
    }

    function clearPrinter() {
        localStorage.removeItem(STORAGE_KEY);
    }

    return {
        initConfig: initConfig,
        printSale: printSale,
        listPrinters: listPrinters,
        setPrinter: setPrinter,
        getSavedPrinter: getSavedPrinter,
        clearPrinter: clearPrinter,
        connect: connect,
    };
})();
