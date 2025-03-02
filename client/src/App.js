import React, { useEffect, useState, useRef } from "react";
import axios from "axios";

export default function App() {
    const [auditData, setAuditData] = useState([]);
    const [smsData, setSmsData] = useState({});
    const [logs, setLogs] = useState([]);
    const [loading, setLoading] = useState(true);
    const [showLogs, setShowLogs] = useState(false);
    const [error, setError] = useState(null);

    const wsRef = useRef(null);
    const abortControllerRef = useRef(new AbortController());

    useEffect(() => {
        fetchAuditData();
        fetchSmsData();
        setupWebSocket();

        const auditInterval = setInterval(fetchAuditData, 10000);
        const smsInterval = setInterval(fetchSmsData, 10000);

        return () => {
            clearInterval(auditInterval);
            clearInterval(smsInterval);
            if (wsRef.current) {
                wsRef.current.close();
            }
            abortControllerRef.current.abort();
        };
    }, []);

    const fetchAuditData = async () => {
        abortControllerRef.current.abort();
        abortControllerRef.current = new AbortController();

        try {
            const response = await axios.get("http://45.152.170.77:7777/audit", {
                signal: abortControllerRef.current.signal,
                timeout: 5000,
            });
            setAuditData(response.data.data);
            setError(null);
        } catch (error) {
            console.error("Ошибка при получении данных аудита:", error);
            setError("Ошибка загрузки данных модемов.");
        }
    };

    const fetchSmsData = async () => {
        abortControllerRef.current.abort();
        abortControllerRef.current = new AbortController();

        try {
            const response = await axios.get("http://45.152.170.77:7777/sms", {
                signal: abortControllerRef.current.signal,
                timeout: 5000,
            });
            setSmsData(response.data.data);
            setLoading(false);
            setError(null);
        } catch (error) {
            console.error("Ошибка при получении SMS:", error);
            setError("Ошибка загрузки SMS.");
        }
    };

    const setupWebSocket = () => {
        if (wsRef.current) {
            wsRef.current.close();
        }

        wsRef.current = new WebSocket("ws://45.152.170.77:7777/ws/logs");

        wsRef.current.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                if (data.status === "LOG") {
                    setLogs((prevLogs) => [...prevLogs.slice(-49), data.message]);
                }
            } catch (error) {
                console.error("Ошибка обработки данных WebSocket:", error);
            }
        };

        wsRef.current.onopen = () => console.log("WebSocket подключён");
        wsRef.current.onerror = (error) => {
            console.error("Ошибка WebSocket:", error);
            setTimeout(setupWebSocket, 5000);
        };
        wsRef.current.onclose = () => {
            console.log("WebSocket отключён. Переподключение...");
            setTimeout(setupWebSocket, 5000);
        };
    };

    const toggleLogs = () => {
        const logContainer = document.querySelector(".log-container");
        if (logContainer) {
            logContainer.classList.toggle("open");
            setShowLogs(!showLogs);
        }
    };

    return (
        <div className="container mx-auto p-4">
            <h1 className="text-2xl font-bold mb-4">GSM Dashboard</h1>

            {error && <p className="text-red-500">{error}</p>}

            <h2 className="text-xl font-semibold mt-4">Модемы</h2>
            {auditData.length > 0 ? (
                <div className="space-y-4">
                    {auditData.map((modem, index) => (
                        <div key={index} className="border p-4 rounded shadow">
                            <p><strong>Порт:</strong> {modem.port}</p>
                            <p><strong>Оператор:</strong> {modem.operator}</p>
                            <p><strong>Телефон:</strong> {modem.phone}</p>
                            <p><strong>Баланс:</strong> {modem.balance}</p>
                        </div>
                    ))}
                </div>
            ) : (
                <p>Данные о модемах отсутствуют.</p>
            )}

            <h2 className="text-xl font-semibold mt-4">SMS</h2>
            {loading ? (
                <p>Загрузка SMS...</p>
            ) : (
                Object.entries(smsData).map(([port, messages]) => (
                    <div key={port} className="border p-4 rounded shadow mt-4">
                        <h3 className="text-lg font-semibold">Порт: {port}</h3>
                        {messages.length > 0 ? (
                            messages.map((sms, index) => (
                                <div key={index} className="border-t pt-2 mt-2">
                                    <p><strong>Отправитель:</strong> {sms.sender}</p>
                                    <p><strong>Сообщение:</strong> {sms.message}</p>
                                    <p><strong>Дата:</strong> {sms.timestamp}</p>
                                </div>
                            ))
                        ) : (
                            <p>Нет сообщений.</p>
                        )}
                    </div>
                ))
            )}

            <button
                className="fixed top-4 right-4 bg-blue-500 text-white px-4 py-2 rounded shadow-lg transition duration-300"
                onClick={toggleLogs}
            >
                {showLogs ? "Скрыть логи" : "Показать логи"}
            </button>

            <div
                className="fixed top-0 right-0 w-80 h-full bg-gray-900 text-white p-4 log-container"
                style={{ overflowY: "auto" }}
            >
                <h2 className="text-lg font-semibold mb-4">Логи</h2>
                <div className="max-h-[85vh] overflow-y-auto border p-2 rounded bg-gray-800">
                    {logs.length > 0 ? (
                        logs.map((log, index) => <p key={index} className="text-sm">{log}</p>)
                    ) : (
                        <p>Логи отсутствуют.</p>
                    )}
                </div>
            </div>
        </div>
    );
}
