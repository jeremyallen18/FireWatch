"""
Generador de Reportes PDF Profesionales
FireWatch - report_generator.py
Módulo para generar reportes en PDF con imágenes, gráficos y estadísticas
"""

import io
import os
from datetime import datetime, timedelta
import matplotlib
matplotlib.use('Agg')  # Backend sin interfaz gráfica
import matplotlib.pyplot as plt
from reportlab.lib.pagesizes import letter
from reportlab.lib.colors import HexColor, black, white, grey
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, Image as RLImage
from reportlab.lib import colors


class ReportGenerator:
    """Genera reportes PDF profesionales con estadísticas e imágenes"""

    def __init__(self, db_manager):
        self.db_manager = db_manager
        self.base_dir = os.path.dirname(os.path.dirname(__file__))
        self.logo_path = os.path.join(self.base_dir, 'static', 'images', 'no-signal.svg')
        self.screenshots_dir = os.path.join(self.base_dir, 'screenshots')

    def generate_pdf(self, detections_data: list, stats: dict) -> bytes:
        """
        Genera un PDF profesional con reportes y gráficos
        
        Args:
            detections_data: Lista de detecciones
            stats: Diccionario de estadísticas
            
        Returns:
            bytes: Contenido del PDF
        """
        pdf_buffer = io.BytesIO()
        
        doc = SimpleDocTemplate(
            pdf_buffer,
            pagesize=letter,
            rightMargin=0.5*inch,
            leftMargin=0.5*inch,
            topMargin=0.5*inch,
            bottomMargin=0.5*inch,
            title="FireWatch - Reporte de Detecciones",
            author="FireWatch Sistema",
            subject="Reporte Profesional de Detecciones de Incendios"
        )
        
        # Estilos
        styles = getSampleStyleSheet()
        
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=HexColor('#FF6B35'),
            spaceAfter=6,
            alignment=1,
            fontName='Helvetica-Bold'
        )
        
        subtitle_style = ParagraphStyle(
            'CustomSubtitle',
            parent=styles['Normal'],
            fontSize=11,
            textColor=HexColor('#666666'),
            spaceAfter=18,
            alignment=1,
            fontName='Helvetica'
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=12,
            textColor=HexColor('#FF6B35'),
            spaceAfter=10,
            fontName='Helvetica-Bold'
        )
        
        normal_style = ParagraphStyle(
            'CustomNormal',
            parent=styles['Normal'],
            fontSize=9,
            textColor=HexColor('#333333'),
            spaceAfter=6,
            fontName='Helvetica'
        )
        
        # Elementos del PDF
        elements = []
        
        # ─── ENCABEZADO ─────────────────────────────────────────────
        elements.append(Paragraph("🔥 FIREWATCH", title_style))
        elements.append(Paragraph(
            "Sistema Automático de Detección de Incendios y Gases",
            subtitle_style
        ))
        
        # ─── INFORMACIÓN DEL REPORTE ────────────────────────────────
        fecha_reporte = datetime.now().strftime('%d/%m/%Y')
        hora_reporte = datetime.now().strftime('%H:%M:%S')
        
        info_data = [
            ['Fecha del Reporte:', fecha_reporte, 'Hora:', hora_reporte],
            ['Generado:', 'Sistema FireWatch', 'Versión:', '1.0'],
        ]
        
        info_table = Table(info_data, colWidths=[1.4*inch, 1.3*inch, 1.4*inch, 1.3*inch])
        info_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (3, 1), HexColor('#F5F5F5')),
            ('TEXTCOLOR', (0, 0), (3, 1), HexColor('#333333')),
            ('ALIGN', (0, 0), (3, 1), 'LEFT'),
            ('FONTNAME', (0, 0), (3, 1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (0, 1), 10),
            ('FONTSIZE', (1, 0), (3, 1), 9),
            ('BOTTOMPADDING', (0, 0), (3, 1), 8),
            ('TOPPADDING', (0, 0), (3, 1), 8),
            ('GRID', (0, 0), (3, 1), 0.5, colors.grey),
        ]))
        
        elements.append(info_table)
        elements.append(Spacer(1, 0.2*inch))
        
        # ─── ESTADÍSTICAS GENERALES ────────────────────────────────
        elements.append(Paragraph("RESUMEN EJECUTIVO", heading_style))
        
        total_detecciones = stats.get('total', 0) or 0
        detecciones_hoy = stats.get('today', 0) or 0
        confianza_promedio = stats.get('avg_confidence', 0) or 0
        alertas_enviadas = stats.get('alerts_sent', 0) or 0
        
        stats_data = [
            ['Total de Registros', str(total_detecciones), 'Detecciones Hoy', str(detecciones_hoy)],
            ['Confianza Promedio', f'{float(confianza_promedio)*100:.1f}%', 'Alertas Enviadas', str(alertas_enviadas)],
        ]
        
        stats_table = Table(stats_data, colWidths=[1.8*inch, 1.2*inch, 1.8*inch, 1.2*inch])
        stats_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (3, 0), HexColor('#FF6B35')),
            ('TEXTCOLOR', (0, 0), (3, 0), white),
            ('ALIGN', (0, 0), (3, 1), 'CENTER'),
            ('FONTNAME', (0, 0), (3, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (3, 0), 10),
            ('FONTNAME', (0, 0), (3, 1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (3, 1), 9),
            ('BOTTOMPADDING', (0, 0), (3, 1), 12),
            ('TOPPADDING', (0, 0), (3, 1), 12),
            ('GRID', (0, 0), (3, 1), 0.5, colors.grey),
            ('BACKGROUND', (0, 1), (3, 1), HexColor('#F0F0F0')),
        ]))
        
        elements.append(stats_table)
        elements.append(Spacer(1, 0.2*inch))
        
        # ─── GRÁFICO DE ESTADÍSTICAS ────────────────────────────────
        try:
            chart_image = self._generate_chart(detections_data, total_detecciones)
            if chart_image:
                elements.append(Paragraph("ANÁLISIS TEMPORAL", heading_style))
                img = RLImage(chart_image, width=6*inch, height=2.5*inch)
                elements.append(img)
                elements.append(Spacer(1, 0.1*inch))
        except Exception as e:
            print(f"[Report] Error al generar gráfico: {e}")
        
        # ─── EVIDENCIA FOTOGRÁFICA ──────────────────────────────────
        try:
            evidence_images = self._get_evidence_images(detections_data)
            if evidence_images:
                elements.append(PageBreak())  # Nueva página para imágenes
                elements.append(Paragraph("EVIDENCIA FOTOGRÁFICA", heading_style))
                elements.append(Spacer(1, 0.1*inch))
                
                for idx, (img_path, timestamp) in enumerate(evidence_images[:5], 1):  # Máximo 5 imágenes
                    try:
                        if os.path.exists(img_path):
                            img = RLImage(img_path, width=5.5*inch, height=3.5*inch)
                            elements.append(img)
                            elements.append(Paragraph(
                                f"<i>Detección #{idx} - {timestamp}</i>",
                                normal_style
                            ))
                            elements.append(Spacer(1, 0.1*inch))
                    except Exception as e:
                        print(f"[Report] Error al incluir imagen {img_path}: {e}")
        except Exception as e:
            print(f"[Report] Error en sección de evidencia: {e}")
        
        # ─── TABLA DE DETECCIONES ───────────────────────────────────
        elements.append(Paragraph("DETALLE DE DETECCIONES", heading_style))
        
        table_data = [['ID', 'Fecha/Hora', 'Confianza', 'Estado', 'Email', 'ESP32']]
        
        for detection in detections_data[:50]:
            timestamp_str = detection.get('timestamp', '')
            if isinstance(timestamp_str, str):
                if 'T' in timestamp_str:
                    fecha, hora = timestamp_str.split('T')
                else:
                    fecha, hora = timestamp_str[:10], timestamp_str[11:19]
            else:
                fecha = detection['timestamp'].strftime('%Y-%m-%d')
                hora = detection['timestamp'].strftime('%H:%M:%S')
            
            confidence_val = detection.get('confidence', 0)
            if isinstance(confidence_val, (int, float)):
                confidence_str = f'{float(confidence_val)*100:.1f}%'
            else:
                confidence_str = str(confidence_val)
            
            email_sent = 'Sí' if detection.get('alert_sent') else 'No'
            esp32_triggered = 'Sí' if detection.get('esp32_triggered') else 'No'
            
            table_data.append([
                str(detection.get('id', '')),
                f"{fecha}\n{hora}",
                confidence_str,
                detection.get('status', '')[:15],
                email_sent,
                esp32_triggered
            ])
        
        detection_table = Table(table_data, colWidths=[0.4*inch, 1.4*inch, 0.9*inch, 1.2*inch, 0.7*inch, 0.7*inch])
        detection_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (5, 0), HexColor('#FF6B35')),
            ('TEXTCOLOR', (0, 0), (5, 0), white),
            ('ALIGN', (0, 0), (5, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (5, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (5, 0), 9),
            ('BOTTOMPADDING', (0, 0), (5, 0), 8),
            ('TOPPADDING', (0, 0), (5, 0), 8),
            
            ('ALIGN', (0, 1), (5, -1), 'CENTER'),
            ('FONTNAME', (0, 1), (5, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (5, -1), 8),
            ('ROWBACKGROUNDS', (0, 1), (5, -1), [white, HexColor('#F9F9F9')]),
            ('GRID', (0, 0), (5, -1), 0.5, colors.grey),
            ('LEFTPADDING', (0, 0), (5, -1), 6),
            ('RIGHTPADDING', (0, 0), (5, -1), 6),
            ('TOPPADDING', (0, 0), (5, -1), 6),
            ('BOTTOMPADDING', (0, 0), (5, -1), 6),
            ('VALIGN', (0, 0), (5, -1), 'MIDDLE'),
        ]))
        
        elements.append(detection_table)
        
        if len(detections_data) > 50:
            elements.append(Spacer(1, 0.1*inch))
            elements.append(Paragraph(
                f"<i>Se muestran 50 de {len(detections_data)} registros disponibles.</i>",
                normal_style
            ))
        
        elements.append(Spacer(1, 0.3*inch))
        
        # ─── PIE DE PÁGINA ──────────────────────────────────────────
        footer_style = ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            fontSize=7,
            textColor=HexColor('#999999'),
            alignment=1,
            fontName='Helvetica'
        )
        
        elements.append(Paragraph(
            "FireWatch — Sistema Automático de Monitoreo de Incendios y Gases | "
            "Reporte Generado Automáticamente | Uso Confidencial",
            footer_style
        ))
        
        # Construir PDF
        doc.build(elements)
        
        pdf_buffer.seek(0)
        return pdf_buffer.getvalue()

    def _generate_chart(self, detections_data: list, total: int = 0) -> io.BytesIO:
        """
        Genera un gráfico de estadísticas temporales
        
        Args:
            detections_data: Lista de detecciones
            total: Total de detecciones
            
        Returns:
            io.BytesIO: Buffer con la imagen del gráfico o None
        """
        try:
            if not detections_data or len(detections_data) < 2:
                return None
            
            # Contar detecciones por hora
            hours = {}
            for detection in detections_data:
                timestamp_str = detection.get('timestamp', '')
                try:
                    if isinstance(timestamp_str, str):
                        if 'T' in timestamp_str:
                            hora = timestamp_str.split('T')[1][:2]
                        else:
                            hora = timestamp_str[11:13]
                    else:
                        hora = detection['timestamp'].strftime('%H')
                    
                    hours[hora] = hours.get(hora, 0) + 1
                except (KeyError, ValueError, TypeError, AttributeError):
                    continue
            
            if not hours:
                return None
            
            # Crear gráfico
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 2.5))
            fig.patch.set_facecolor('white')
            
            # Gráfico de línea: Detecciones por hora
            horas_sorted = sorted(hours.keys())
            valores = [hours[h] for h in horas_sorted]
            
            ax1.plot(horas_sorted, valores, marker='o', color='#FF6B35', linewidth=2, markersize=6)
            ax1.fill_between(range(len(horas_sorted)), valores, alpha=0.3, color='#FF6B35')
            ax1.set_title('Detecciones por Hora', fontsize=10, fontweight='bold', color='#333')
            ax1.set_xlabel('Hora del Día', fontsize=9)
            ax1.set_ylabel('Cantidad', fontsize=9)
            ax1.grid(True, alpha=0.3)
            ax1.set_facecolor('#F9F9F9')
            
            # Gráfico de pastel: Alertas enviadas vs No enviadas
            alertas_data = [d for d in detections_data if d.get('alert_sent')]
            sin_alertas = len(detections_data) - len(alertas_data)
            
            sizes = [len(alertas_data), sin_alertas]
            colors_pie = ['#FF6B35', '#CCCCCC']
            labels_pie = ['Alertas Enviadas', 'Sin Alertas']
            
            ax2.pie(sizes, labels=labels_pie, colors=colors_pie, autopct='%1.1f%%',
                   startangle=90, textprops={'fontsize': 9})
            ax2.set_title('Estado de Alertas', fontsize=10, fontweight='bold', color='#333')
            
            plt.tight_layout()
            
            # Guardar en buffer
            chart_buffer = io.BytesIO()
            plt.savefig(chart_buffer, format='png', dpi=100, bbox_inches='tight', facecolor='white')
            chart_buffer.seek(0)
            plt.close(fig)
            
            return chart_buffer
            
        except Exception as e:
            print(f"[Report] Error en _generate_chart: {e}")
            return None

    def get_last_detection_image(self) -> str:
        """
        Obtiene la ruta de la última imagen de detección si existe
        
        Returns:
            str: Ruta de la imagen o None
        """
        try:
            if not os.path.exists(self.screenshots_dir):
                return None
            
            files = [f for f in os.listdir(self.screenshots_dir) if f.lower().endswith(('.jpg', '.png'))]
            if not files:
                return None
            
            # Ordenar por fecha de modificación
            files.sort(key=lambda f: os.path.getmtime(os.path.join(self.screenshots_dir, f)), reverse=True)
            return os.path.join(self.screenshots_dir, files[0])
            
        except Exception as e:
            print(f"[Report] Error al obtener imagen de detección: {e}")
            return None

    def _get_evidence_images(self, detections_data: list) -> list:
        """
        Obtiene las rutas físicas de las imágenes asociadas a las detecciones
        
        Args:
            detections_data: Lista de detecciones de la BD
            
        Returns:
            list: Lista de tuplas (ruta_física, timestamp) de imágenes existentes
        """
        try:
            evidence = []
            
            # Recopilar imágenes de las detecciones
            for detection in detections_data:
                image_path = detection.get('image_path', '')
                if not image_path:
                    continue
                
                # Construir ruta física completa
                if image_path.startswith('screenshots/'):
                    full_path = os.path.join(self.base_dir, image_path)
                else:
                    full_path = os.path.join(self.base_dir, 'screenshots', image_path)
                
                # Verificar que existe
                if os.path.exists(full_path):
                    timestamp_str = detection.get('timestamp', 'N/A')
                    if isinstance(timestamp_str, str):
                        if 'T' in timestamp_str:
                            fecha, hora = timestamp_str.split('T')
                            timestamp_str = f"{fecha} {hora[:8]}"
                    evidence.append((full_path, timestamp_str))
            
            # Ordenar por fecha descendente (más recientes primero)
            evidence.sort(key=lambda x: x[1], reverse=True)
            
            return evidence
            
        except Exception as e:
            print(f"[Report] Error en _get_evidence_images: {e}")
            return []
