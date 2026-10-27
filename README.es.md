# omarchy-cooler-lcd-5131 · v0.0.1

[English](README.md) · **Español**

Servicio de Omarchy para la pequeña pantalla de temperatura de disipadores de
CPU con USB **5131:2007** y **protocolo HID 0x40**. Solo biblioteca estándar de
Python 3; sin compilador, paquetes pip ni archivo de configuración. No hay
widget en la barra, panel ni icono.

Verificado con el **ARGB Air Cool** de fábrica de un CyberPowerPC **GMA6000BSTV6**
(ASRock B840M-C, Ryzen 7 8700F, RX 9060); el prototipo encendió la pantalla a 42 °C.

## Identificar el dispositivo

```sh
lsusb | grep 5131:2007
```

El dispositivo no tiene descriptores de texto USB. `lsusb` puede llamarlo
**MSR-101U magnetic card reader** por la entrada de su base de datos USB.

Solo se admite la **familia 0x40** (CSM / Alseye / COOLMOON / THERMAX 6 Pulsar).
Otro firmware con el mismo identificador USB usa **opcodes 0x00/0x01/0x02** y
no es compatible. El identificador USB no permite distinguirlos; este driver
nunca sondea ni cambia de protocolo. Úsalo solo con la familia verificada.

## Instalar

Requiere Omarchy Shell con plugins de servicio, Python 3 y systemd. `lsusb` y
`notify-send` son las herramientas habituales de Omarchy; `nvidia-smi` es opcional.

```sh
omarchy plugin add https://github.com/gsus67/omarchy-cooler-lcd-5131 --enable
```

Al cargarse, el plugin instala y activa
`~/.config/systemd/user/omarchy-cooler-lcd-5131.service`, apuntando a su checkout.
Se ejecuta con tu usuario de escritorio. Nunca instala paquetes ni pide sudo.

Ejecuta el único paso privilegiado desde una terminal:

```sh
sudo bash ~/.config/omarchy/plugins/io.github.gsus67.omarchy-cooler-lcd-5131/setup.sh
```

Esto instala de forma idempotente la regla propiedad de root con modo 0644
`/etc/udev/rules.d/70-omarchy-cooler-lcd-5131.rules`, recarga udev y dispara hidraw:

```udev
SUBSYSTEM=="hidraw", ATTRS{idVendor}=="5131", ATTRS{idProduct}=="2007", TAG+="uaccess"
```

El acceso corresponde a la sesión local activa; no se usan permisos de
escritura global ni grupos adicionales. Reconecta el USB si hace falta. Al
cargarse con un dispositivo sin permiso de escritura, el plugin envía una
sola notificación con este comando de preparación.

## Qué recibe la pantalla

Cada segundo: temperatura de CPU y GPU en **°C**, uso %, frecuencia MHz,
ventilador RPM, consumo W y fecha y hora local. El firmware controla el diseño
y decide qué campos se ven. Los valores ausentes o ilegibles son **0**.

- CPU: `k10temp` Tctl, paquete de `coretemp` o `zenpower`; uso desde `/proc/stat`,
  frecuencia desde cpufreq. Solo se usan ventiladores etiquetados explícitamente
  como CPU. El consumo procede de hwmon de CPU o contadores RAPL de paquete legibles.
- GPU: hwmon de `amdgpu` y `gpu_busy_percent`; `nvidia-smi` opcional para NVIDIA;
  lectura de sysfs de Intel `i915`/`xe` cuando existe. Se usa una GPU. Las RPM del
  ventilador NVIDIA no están disponibles y quedan en 0.
- El ventilador y consumo de CPU suelen quedar en 0 sin sensores accesibles.
  No se amplían permisos ni se cambia el modo de los contadores RAPL.

El servicio redescubre el dispositivo HID por `HID_ID` cada segundo, incluso
tras desconexión o suspensión. Nunca supone un `/dev/hidrawN` fijo. La unidad
de usuario protegida tiene el sistema de archivos de solo lectura, directorio
temporal privado, ningún privilegio nuevo y solo sockets Unix; conserva acceso
a los dispositivos USB reales. Al detenerse, la pantalla conserva el último
frame. No hay opciones; Celsius y un segundo son fijos. El bit Fahrenheit del
protocolo está documentado en el constructor de frames, pero nunca se envía.

```sh
systemctl --user status omarchy-cooler-lcd-5131.service
journalctl --user -u omarchy-cooler-lcd-5131.service
omarchy plugin update io.github.gsus67.omarchy-cooler-lcd-5131
```

Desactivar solo el plugin del shell no detiene la unidad de usuario independiente.
Para detenerla, usa `systemctl --user stop omarchy-cooler-lcd-5131.service`.

## Desinstalar

Ejecuta con tu usuario de escritorio. El script desactiva el plugin, detiene y
elimina la unidad de usuario y cualquier configuración antigua del plugin, y
pide sudo solo para eliminar la regla udev. Después elimina el checkout:

```sh
bash ~/.config/omarchy/plugins/io.github.gsus67.omarchy-cooler-lcd-5131/uninstall.sh
omarchy plugin remove io.github.gsus67.omarchy-cooler-lcd-5131
```

La unidad de usuario respeta `XDG_CONFIG_HOME`. El daemon no guarda estado ni ajustes.

## Desarrollo

```sh
python -m unittest discover -s tests
omarchy plugin validate .
```

Los tests usan árboles sysfs temporales y comandos del sistema simulados, sin
tocar hardware. CI también verifica la unidad generada con `systemd-analyze
verify`, todos los scripts con ShellCheck, los workflows con zizmor y
Python/actions con CodeQL. Consulta [SECURITY.md](SECURITY.md).

Licencia **GPL-3.0-or-later**. Gracias a
[YehanKD/csm-cooler-lcd](https://github.com/YehanKD/csm-cooler-lcd),
[ZarateBM/thermax-pulsar-linux](https://github.com/ZarateBM/thermax-pulsar-linux)
y [omarchy-trcc](https://github.com/gsus67/omarchy-trcc).
Créditos del protocolo y del código en [NOTICE.md](NOTICE.md).
