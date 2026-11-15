import { useState } from "react";
import { Alert, Button, Card, Form, Input, Typography } from "antd";
import { LockOutlined, UserOutlined } from "@ant-design/icons";
import { ErrorApi, pedir } from "../api";
import type { Usuario } from "../tipos";
import Logo from "./Logo";

interface Props {
  onIngreso: (usuario: Usuario) => void;
  aviso?: string;
}

export default function Login({ onIngreso, aviso }: Props) {
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<string>();

  async function ingresar(valores: { usuario: string; password: string }) {
    setEnviando(true);
    setError(undefined);
    try {
      onIngreso(await pedir<Usuario>("/api/auth/login", { metodo: "POST", cuerpo: valores }));
    } catch (e) {
      setError(e instanceof ErrorApi ? e.message : "No se pudo iniciar sesión.");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <main className="login">
      <Card className="login-tarjeta">
        <div className="login-marca">
          <Logo tamano={40} />
          <div>
            <Typography.Title level={3} style={{ margin: 0 }}>
              Faro
            </Typography.Title>
            <Typography.Text type="secondary">Analítica inteligente de ventas</Typography.Text>
          </div>
        </div>
        {aviso && <Alert type="info" showIcon title={aviso} style={{ marginBottom: 16 }} />}
        {error && <Alert type="error" showIcon title={error} style={{ marginBottom: 16 }} role="alert" />}
        <Form layout="vertical" onFinish={ingresar} requiredMark={false} disabled={enviando}>
          <Form.Item
            label="Usuario"
            name="usuario"
            rules={[{ required: true, message: "Escribe tu usuario" }]}
          >
            <Input prefix={<UserOutlined />} autoComplete="username" autoFocus />
          </Form.Item>
          <Form.Item
            label="Contraseña"
            name="password"
            rules={[{ required: true, message: "Escribe tu contraseña" }]}
          >
            <Input.Password prefix={<LockOutlined />} autoComplete="current-password" />
          </Form.Item>
          <Button type="primary" htmlType="submit" block loading={enviando}>
            Ingresar
          </Button>
        </Form>
      </Card>
    </main>
  );
}
