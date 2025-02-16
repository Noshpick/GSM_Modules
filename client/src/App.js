import React, { useEffect, useState } from "react";
import axios from "axios";

export default function App() {
    const [auditData, setAuditData] = useState([]);
    const [smsData, setSmsData] = useState({});
    const [logs, setLogs] = useState([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        fetchAuditData();
        fetchSmsData();
        fetchLogs();

        const smsInterval = setInterval(fetchSmsData, 10000);
        const logInterval = setInterval(fetchLogs, 5000);

        return () => {
            clearInterval(smsInterval);
            clearInterval(logInterval);
        };
    }, []);

    const fetchAuditData = async () => {
        try {
            const response = await axios.get("http://localhost:7777/audit");
            setAuditData(response.data.data);
        } catch (error) {
            console.error("Ошибка при получении данных аудита:", error);
        }
    };

    const fetchSmsData = async () => {
        try {
            const response = await axios.get("http://localhost:7777/sms");
            setSmsData(response.data.data);
            setLoading(false);
        } catch (error) {
            console.error("Ошибка при получении SMS:", error);
        }
    };

    const fetchLogs = async () => {
        try {
            const response = await axios.get("http://localhost:7777/logs");
            setLogs(response.data.logs || []);
        } catch (error) {
            console.error("Ошибка при получении логов:", error);
        }
    };

    return (
        <div className="container mx-auto p-4">
            <h1 className="text-2xl font-bold mb-4">GSM Dashboard</h1>

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

            <h2 className="text-xl font-semibold mt-4">Логи</h2>
            <div className="border p-4 rounded shadow mt-4 bg-gray-100 max-h-60 overflow-y-auto">
                {logs.length > 0 ? (
                    logs.map((log, index) => <p key={index} className="text-sm">{log}</p>)
                ) : (
                    <p>Логи отсутствуют.</p>
                )}
            </div>
        </div>
    );
}
