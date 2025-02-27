import React, { useEffect, useState } from "react";
import axios from "axios";

export default function App() {
    const [auditData, setAuditData] = useState([]);
    const [smsData, setSmsData] = useState({});
    const [logs, setLogs] = useState([]);
    const [showLogs, setShowLogs] = useState(false);
    const [selectedModem, setSelectedModem] = useState(null);
    const [selectedSms, setSelectedSms] = useState([]);

    useEffect(() => {
        fetchAuditData();
        fetchSmsData();
        setupWebSocket();

        const smsInterval = setInterval(fetchSmsData, 10000);
        return () => clearInterval(smsInterval);
    }, []);

    const fetchAuditData = async () => {
        try {
            const response = await axios.get("http://45.152.170.77:7777/audit");
            console.log("Ответ API (модемы):", response.data);
            setAuditData(response.data.data);
        } catch (error) {
            console.error("Ошибка при получении данных аудита:", error);
        }
    };

    const fetchSmsData = async () => {
        try {
            const response = await axios.get("http://45.152.170.77:7777/sms");
            console.log("Ответ API (SMS):", response.data);
            setSmsData(response.data.data);
        } catch (error) {
            console.error("Ошибка при получении SMS:", error);
        }
    };

    const setupWebSocket = () => {
        const ws = new WebSocket("ws://45.152.170.77:7777/ws/logs");

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (data.status === "LOG") {
                setLogs((prevLogs) => [...prevLogs.slice(-49), data.message]);
            }
        };

        ws.onopen = () => console.log("WebSocket подключён");
        ws.onerror = (error) => console.error("Ошибка WebSocket:", error);
        ws.onclose = () => console.log("WebSocket отключён");
    };

    const toggleLogs = () => {
        document.querySelector(".log-container")?.classList.toggle("open");
        setShowLogs(!showLogs);
    };

    const openSmsPanel = (modem) => {
        setSelectedModem(modem);
        setSelectedSms(smsData[modem.port] || []);
        document.querySelector(".sms-container")?.classList.add("open");
    };

    const closeSmsPanel = () => {
        document.querySelector(".sms-container")?.classList.remove("open");
        setSelectedModem(null);
    };

    return (
        <div className="container mx-auto p-4">
            <h1 className="text-2xl font-bold mb-4">GSM Dashboard</h1>

            <h2 className="text-xl font-semibold mt-4">Модемы</h2>
            {auditData.length > 0 ? (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {auditData.map((modem, index) => (
                        <div 
                            key={index} 
                            className="border p-4 rounded shadow cursor-pointer bg-white hover:bg-gray-100 transition"
                            onClick={() => openSmsPanel(modem)}
                        >
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

            <button 
                className="fixed top-4 right-4 bg-blue-500 text-white px-4 py-2 rounded shadow-lg transition duration-300"
                onClick={toggleLogs}
            >
                {showLogs ? "Скрыть логи" : "Показать логи"}
            </button>

            <div className="fixed top-0 right-0 w-80 h-full bg-gray-900 text-white p-4 log-container">
                <h2 className="text-lg font-semibold mb-4">Логи</h2>
                <div className="h-[90vh] overflow-y-auto border p-2 rounded bg-gray-800">
                    {logs.length > 0 ? logs.map((log, index) => <p key={index} className="text-sm">{log}</p>) : <p>Логи отсутствуют.</p>}
                </div>
            </div>

            <div className="fixed top-0 right-0 w-96 h-full bg-gray-900 text-white p-4 sms-container hidden">
                <button className="absolute top-4 right-4 bg-red-500 text-white px-3 py-1 rounded" onClick={closeSmsPanel}>X</button>
                {selectedModem ? (
                    <>
                        <h2 className="text-lg font-semibold mb-4">SMS ({selectedModem.port})</h2>
                        <div className="h-[85vh] overflow-y-auto border p-2 rounded bg-gray-800">
                            {selectedSms.length > 0 ? selectedSms.map((sms, index) => (
                                <div key={index} className="border-b pb-2 mb-2">
                                    <p><strong>От:</strong> {sms.sender}</p>
                                    <p><strong>Сообщение:</strong> {sms.message}</p>
                                    <p><strong>Дата:</strong> {sms.timestamp}</p>
                                </div>
                            )) : <p>Нет сообщений.</p>}
                        </div>
                    </>
                ) : (
                    <p>Выберите модем, чтобы увидеть SMS.</p>
                )}
            </div>
        </div>
    );
}
