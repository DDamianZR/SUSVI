import os
import uuid
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, ListFlowable, ListItem
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT

class URBANIAReportGenerator:
    """Generador principal de reportes ejecutivos en PDF para URBANIA."""
    
    def __init__(self):
        self.colors = {
            'black': colors.HexColor('#1A1A1A'),
            'gray': colors.HexColor('#555555'),
            'green': colors.HexColor('#16a34a'),
            'red': colors.HexColor('#dc2626'),
            'amber': colors.HexColor('#d97706'),
            'bg_alt': colors.HexColor('#F9F9F9'),
            'white': colors.white,
            'blue': colors.HexColor('#2563eb')
        }
        self.styles = getSampleStyleSheet()
        self._setup_styles()

    def _setup_styles(self):
        """Configura los estilos de parrafo y tipografia de ReportLab."""
        self.styles.add(ParagraphStyle(
            name='PortadaTitle',
            fontName='Helvetica-Bold',
            fontSize=48,
            textColor=self.colors['black'],
            alignment=TA_CENTER,
            spaceAfter=20
        ))
        
        self.styles.add(ParagraphStyle(
            name='PortadaSubtitle',
            fontName='Helvetica',
            fontSize=18,
            textColor=self.colors['gray'],
            alignment=TA_CENTER,
            spaceAfter=40
        ))
        
        self.styles.add(ParagraphStyle(
            name='PortadaMeta',
            fontName='Helvetica-Bold',
            fontSize=12,
            textColor=self.colors['gray'],
            alignment=TA_CENTER,
            spaceAfter=10
        ))
        
        self.styles.add(ParagraphStyle(
            name='SectionTitle',
            fontName='Helvetica-Bold',
            fontSize=18,
            textColor=self.colors['black'],
            spaceAfter=15,
            spaceBefore=20
        ))

        self.styles.add(ParagraphStyle(
            name='BodyTextCustom',
            fontName='Helvetica',
            fontSize=11,
            textColor=self.colors['gray'],
            leading=16,
            spaceAfter=12
        ))
        
        self.styles.add(ParagraphStyle(
            name='WarningText',
            fontName='Helvetica',
            fontSize=11,
            textColor=self.colors['red'],
            leading=16,
            spaceAfter=8
        ))

        self.styles.add(ParagraphStyle(
            name='FooterText',
            fontName='Helvetica',
            fontSize=9,
            textColor=self.colors['gray'],
            alignment=TA_CENTER
        ))

    def _format_currency(self, val):
        try:
            return f"${float(val):,.0f} MXN"
        except:
            return str(val)

    def generate(self, report_data: dict, output_path: str) -> str:
        """
        Genera el PDF a partir del dict formateado y lo guarda en output_path.
        
        Args:
            report_data: dict con metadata, resumen, escenarios, advertencias, etc.
            output_path: ruta absoluta donde guardar el PDF.
            
        Returns:
            La misma ruta de output.
        """
        doc = SimpleDocTemplate(
            output_path, 
            pagesize=letter,
            rightMargin=50, leftMargin=50,
            topMargin=50, bottomMargin=50
        )
        Story = []
        
        metadata = report_data.get('metadata', {})
        fecha = datetime.fromisoformat(metadata.get('timestamp', datetime.now().isoformat().replace('Z', '+00:00'))).strftime("%d/%m/%Y %H:%M")
        sector = str(metadata.get('sector', 'N/D')).upper()
        manzanas = metadata.get('n_manzanas_analizadas', 0)
        
        # ── PAGINA 1: PORTADA ──
        Story.append(Spacer(1, 150))
        Story.append(Paragraph("URBANIA", self.styles['PortadaTitle']))
        Story.append(Paragraph("Reporte de Inteligencia Territorial", self.styles['PortadaSubtitle']))
        
        # Linea separadora (hacky line via table)
        line_data = [['']]
        t_line = Table(line_data, colWidths=[400])
        t_line.setStyle(TableStyle([
            ('LINEBELOW', (0,0), (-1,-1), 1.5, self.colors['black']),
        ]))
        Story.append(t_line)
        Story.append(Spacer(1, 40))
        
        Story.append(Paragraph(f"Sector Industrial: <font color='#2563eb'>{sector}</font>", self.styles['PortadaMeta']))
        Story.append(Paragraph(f"Manzanas Analizadas: {manzanas}", self.styles['PortadaMeta']))
        Story.append(Paragraph(f"Fecha de Computo: {fecha}", self.styles['PortadaMeta']))
        Story.append(Paragraph(f"Analysis ID: {report_data.get('analysis_id', 'N/A')}", self.styles['PortadaMeta']))
        
        Story.append(Spacer(1, 150))
        Story.append(Paragraph("Generado por URBANIA · XOLUM — <i>IBM Watsonx AI</i>", self.styles['FooterText']))
        Story.append(PageBreak())
        
        # ── PAGINA 2: RESUMEN EJECUTIVO ──
        Story.append(Paragraph("RESUMEN EJECUTIVO", self.styles['SectionTitle']))
        resumen_texto = report_data.get('business_resumen', '')
        
        # Limitar maximo ~300 palabras heuristico
        palabras = resumen_texto.split()
        if len(palabras) > 300:
            resumen_texto = " ".join(palabras[:300]) + "..."
            
        Story.append(Paragraph(resumen_texto, self.styles['BodyTextCustom']))
        Story.append(Spacer(1, 20))
        
        # 4 KPIs
        Story.append(Paragraph("Métricas Territoriales Globales", self.styles['SectionTitle']))
        
        kpis = report_data.get('kpis', {'verdes': 'N/D', 'cautela': 'N/D', 'descarte': 'N/D'})
        kpi_data = [
            ['Total Manzanas', 'Zonas Verdes', 'Zonas Cautela', 'Zonas Descarte'],
            [
                str(manzanas), 
                str(kpis.get('verdes', '-')), 
                str(kpis.get('cautela', '-')), 
                str(kpis.get('descarte', '-'))
            ]
        ]
        t_kpi = Table(kpi_data, colWidths=[120, 120, 120, 120])
        t_kpi.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), self.colors['black']),
            ('TEXTCOLOR', (0,0), (-1,0), self.colors['white']),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,0), 10),
            ('BOTTOMPADDING', (0,0), (-1,0), 8),
            # Valores
            ('FONTNAME', (0,1), (-1,1), 'Helvetica-Bold'),
            ('FONTSIZE', (0,1), (-1,1), 16),
            ('TEXTCOLOR', (0,1), (0,1), self.colors['blue']),
            ('TEXTCOLOR', (1,1), (1,1), self.colors['green']),
            ('TEXTCOLOR', (2,1), (2,1), self.colors['amber']),
            ('TEXTCOLOR', (3,1), (3,1), self.colors['red']),
            ('BACKGROUND', (0,1), (-1,1), self.colors['bg_alt']),
            ('BOX', (0,0), (-1,-1), 0.5, self.colors['gray']),
            ('INNERGRID', (0,0), (-1,-1), 0.5, self.colors['gray']),
        ]))
        Story.append(t_kpi)
        
        Story.append(Spacer(1, 30))
        Story.append(Paragraph("Recomendación Final Consolidada", self.styles['SectionTitle']))
        reco = report_data.get('business_recomendacion', '')
        Story.append(Paragraph(reco, self.styles['BodyTextCustom']))
        
        Story.append(PageBreak())
        
        # ── PAGINA 3: TABLA COMPARATIVA DE ESCENARIOS ──
        Story.append(Paragraph("VISIÓN COMPARATIVA DE ESCENARIOS", self.styles['SectionTitle']))
        Story.append(Spacer(1, 10))
        
        scenarios = report_data.get('business_escenarios', [])
        
        table_data = [['Escenario', 'ROI (5A)', 'Payback', 'Exposición Máx', 'Zonas']]
        for sc in scenarios:
            nom = sc.get('nombre', '').upper()
            table_data.append([
                nom,
                f"{sc.get('roi', 0)}%",
                f"{sc.get('payback', 0)} años",
                self._format_currency(sc.get('exposicion', 0) * 1000000), # Viene as M en raw dict? Asumiremos viene literal de python
                str(len(sc.get('zonas_seleccionadas', sc.get('zonas', [])))) # Ajuste si no tiene length directo
            ])
            
        t_sc = Table(table_data, colWidths=[110, 80, 80, 130, 80])
        ts = TableStyle([
            ('BACKGROUND', (0,0), (-1,0), self.colors['black']),
            ('TEXTCOLOR', (0,0), (-1,0), self.colors['white']),
            ('ALIGN', (0,0), (-1,0), 'CENTER'),
            ('ALIGN', (1,1), (-1,-1), 'RIGHT'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0,0), (-1,-1), 8),
            ('TOPPADDING', (0,0), (-1,-1), 8),
            ('GRID', (0,0), (-1,-1), 0.5, self.colors['gray'])
        ])
        
        # Alternar colores e identificar EQUILIBRADO
        for i, row in enumerate(table_data[1:], start=1):
            if i % 2 == 0:
                ts.add('BACKGROUND', (0,i), (-1,i), self.colors['bg_alt'])
            if row[0] == 'EQUILIBRADO':
                ts.add('FONTNAME', (0,i), (-1,i), 'Helvetica-Bold')
                ts.add('TEXTCOLOR', (0,i), (-1,i), self.colors['blue'])
                
        t_sc.setStyle(ts)
        Story.append(t_sc)
        
        # ── PAGINAS 4-6: ANALISIS DETALLADO ──
        for sc in scenarios:
            Story.append(PageBreak())
            nombre = sc.get('nombre', 'Desconocido').upper()
            Story.append(Paragraph(f"ESCENARIO: {nombre}", self.styles['SectionTitle']))
            
            Story.append(Paragraph("<strong>Resumen Narrativo:</strong>", self.styles['BodyTextCustom']))
            Story.append(Paragraph(sc.get('recomendacion_narrativa', ''), self.styles['BodyTextCustom']))
            Story.append(Spacer(1, 15))
            
            # Subtabla de metricas del escenario
            m_data = [
                ['ROI Estimado', 'Payback Period', 'Exposición Máxima'],
                [f"{sc.get('roi', 0)}%", f"{sc.get('payback', 0)} años", self._format_currency(sc.get('exposicion', 0) * 1000000)]
            ]
            t_m = Table(m_data, colWidths=[160, 160, 160])
            t_m.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), self.colors['gray']),
                ('TEXTCOLOR', (0,0), (-1,0), self.colors['white']),
                ('FONTNAME', (0,0), (-1,-1), 'Helvetica-Bold'),
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('GRID', (0,0), (-1,-1), 0.5, self.colors['gray']),
                ('BOTTOMPADDING', (0,0), (-1,-1), 8)
            ]))
            Story.append(t_m)
            
        Story.append(PageBreak())
        
        # ── ULTIMA PAGINA: ADVERTENCIAS Y PASOS ──
        Story.append(Paragraph("ADVERTENCIAS DE RIESGO ESTRATÉGICAS", self.styles['SectionTitle']))
        advs = report_data.get('business_advertencias', [])
        if advs:
            for ad in advs:
                Story.append(Paragraph(f"▲ <b>PRECAUCIÓN:</b> {ad}", self.styles['WarningText']))
        else:
            Story.append(Paragraph("No hay advertencias críticas destacadas.", self.styles['BodyTextCustom']))
            
        Story.append(Spacer(1, 20))
        Story.append(Paragraph("PRÓXIMOS PASOS RECOMENDADOS", self.styles['SectionTitle']))
        
        pasos = report_data.get('business_pasos', [])
        if pasos:
            list_items = [ListItem(Paragraph(p, self.styles['BodyTextCustom']), leftIndent=15, bulletOffsetY=0) for p in pasos]
            Story.append(ListFlowable(list_items, bulletType='1', bulletFontName='Helvetica-Bold'))
        else:
            Story.append(Paragraph("No hay próximos pasos definidos.", self.styles['BodyTextCustom']))
            
        Story.append(Spacer(1, 100))
        Story.append(Paragraph("Confidencial — Generado por URBANIA · XOLUM · IBM Watsonx AI", self.styles['FooterText']))
        
        # GO!
        doc.build(Story)
        return output_path
