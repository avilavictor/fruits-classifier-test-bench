import pandas as pd
from pathlib import Path
from scipy.stats import ttest_ind, mannwhitneyu, shapiro
import matplotlib.pyplot as plt
import seaborn as sns

complete_data = []
events_timing = []
base_path = Path("./logs")
output_path = Path("./processed_data")

def p50(x): return x.quantile(0.50)
def p90(x): return x.quantile(0.90)
def p95(x): return x.quantile(0.95)

def load_metrics_file(path: Path):
    # Iterate over methods (container and standalone)
    for method_folder in base_path.iterdir():
        if not method_folder.is_dir(): 
            continue
        method = method_folder.name 
        
        # Iterate over runs (e.g., run_1, run_2, ..., run_10)
        for run_folder in method_folder.iterdir():
            if not run_folder.is_dir(): 
                continue

            #Strip 'run_' prefix and convert to integer
            run = int(run_folder.name.replace("run_", ""))
            
            # Iterate over CSV files
            for csv_file in run_folder.glob("*_metrics.csv"):
                application = csv_file.stem.replace("_metrics", "")
                
                # Read CSV parsing the timestamp column
                df_temp = pd.read_csv(csv_file, parse_dates=['timestamp'])
                
                # Add context columns
                df_temp['method'] = method
                df_temp['run'] = run
                df_temp['application'] = application

                if application != 'system':
                    # Calculate relative timestamp in seconds and overwrite the original column
                    initial_time = df_temp['timestamp'].min()
                    df_temp['timestamp'] = (df_temp['timestamp'] - initial_time).dt.total_seconds()
                    
                    # Convert memory to MB
                    df_temp['memory_mb'] = df_temp['classifier_memory_kb'] / 1024
                    
                    # Select and reorder only the requested columns
                    # This automatically drops 'cpu_total_ms' and 'classifier_memory_kb'
                    columns_to_keep = ['method', 'run', 'application', 'timestamp', 'cpu_percent', 'memory_mb']
                    df_temp = df_temp[columns_to_keep]
                    
                    complete_data.append(df_temp)
                else:
                    initial_time = df_temp['timestamp'].min()
                    df_temp['timestamp'] = (df_temp['timestamp'] - initial_time).dt.total_seconds()
                    
                    # Convert memory to MB
                    df_temp['memory_mb'] = df_temp['memory_usage_kb'] / 1024
                    df_temp['cpu_percent'] = df_temp['cpu_percentage']
                    
                    # Select and reorder only the requested columns
                    # This automatically drops 'cpu_total_ms' and 'classifier_memory_kb'
                    columns_to_keep = ['method', 'run', 'application', 'timestamp', 'cpu_percent', 'memory_mb', 'cpu_temperature_c', 'cpu_frequency_khz']
                    df_temp = df_temp[columns_to_keep]
                    
                    complete_data.append(df_temp)

    return pd.concat(complete_data, ignore_index=True)

def load_events_file(path: Path):
    # Iterate over methods (container and standalone)
    for method_folder in base_path.iterdir():
        if not method_folder.is_dir(): 
            continue
        method = method_folder.name 
        
        # Iterate over runs (e.g., run_1, run_2, ..., run_10)
        for run_folder in method_folder.iterdir():
            if not run_folder.is_dir(): 
                continue

            #Strip 'run_' prefix and convert to integer
            run = int(run_folder.name.replace("run_", ""))
            temp_events_timing = []
            df_events = pd.DataFrame()
            # Iterate over CSV files
            for events_file in run_folder.glob("*_events.log"):
                
                colunas = ['timestamp', 'event_type', 'image_id']
                
                df_temp = pd.read_csv(events_file, sep=r'\s+\|\s+', names=colunas, engine='python')
                temp_events_timing.append(df_temp)

            df_events = pd.concat(temp_events_timing, ignore_index=True)
            df_events['timestamp'] = pd.to_datetime(df_events['timestamp'])
            df_pivot = df_events.pivot(index='image_id', columns='event_type', values='timestamp')
    
            df_temp = pd.DataFrame(index=df_pivot.index)
            df_temp['timestamp'] = df_pivot['REQUEST_SENT']
            df_temp['time_to_receive_ms'] = (df_pivot['REQUEST_RECEIVED'] - df_pivot['REQUEST_SENT']).dt.total_seconds() * 1000
            df_temp['time_to_process_ms'] = (df_pivot['RESPONSE_SENT'] - df_pivot['REQUEST_RECEIVED']).dt.total_seconds() * 1000
            df_temp['time_to_return_ms'] = (df_pivot['RESPONSE_RECEIVED'] - df_pivot['RESPONSE_SENT']).dt.total_seconds() * 1000
            df_temp['total_time_ms'] = (df_pivot['RESPONSE_RECEIVED'] - df_pivot['REQUEST_SENT']).dt.total_seconds() * 1000
            
            initial_time = df_temp['timestamp'].min()
            df_temp['timestamp'] = (df_temp['timestamp'] - initial_time).dt.total_seconds()    

            df_temp = df_temp.reset_index()
            df_temp['method'] = method
            df_temp['run'] = run

            events_timing.append(df_temp)
    
    return pd.concat(events_timing, ignore_index=True)

def calculate_event_statistics(df_events):
    # Group by method and run, then calculate the required statistics
    grouped = df_events.groupby(['method', 'run']).agg(
        time_to_receive_mean=('time_to_receive_ms', 'mean'),
        time_to_receive_std=('time_to_receive_ms', 'std'),
        time_to_receive_p50=('time_to_receive_ms', p50),
        time_to_receive_p90=('time_to_receive_ms', p90),
        time_to_receive_p95=('time_to_receive_ms', p95),
        time_to_process_mean=('time_to_process_ms', 'mean'),
        time_to_process_std=('time_to_process_ms', 'std'),
        time_to_process_p50=('time_to_process_ms', p50),
        time_to_process_p90=('time_to_process_ms', p90),
        time_to_process_p95=('time_to_process_ms', p95),
        time_to_return_mean=('time_to_return_ms', 'mean'),
        time_to_return_std=('time_to_return_ms', 'std'),
        time_to_return_p50=('time_to_return_ms', p50),
        time_to_return_p90=('time_to_return_ms', p90),
        time_to_return_p95=('time_to_return_ms', p95),
        total_time_mean=('total_time_ms', 'mean'),
        total_time_std=('total_time_ms', 'std'),
        total_time_p50=('total_time_ms', p50),
        total_time_p90=('total_time_ms', p90),
        total_time_p95=('total_time_ms', p95)
    ).reset_index()

    return grouped

def calculate_metrics_statistics(df_metrics):
    # Group by method and run, then calculate the required statistics
    grouped = df_metrics.groupby(['method', 'run', 'application']).agg(
        memory_mb_mean=('memory_mb', 'mean'),
        memory_mb_std=('memory_mb', 'std'),
        memory_mb_p50=('memory_mb', p50),
        memory_mb_p90=('memory_mb', p90),
        memory_mb_p95=('memory_mb', p95),
        cpu_percent_mean=('cpu_percent', 'mean'),
        cpu_percent_std=('cpu_percent', 'std'),
        cpu_percent_p50=('cpu_percent', p50),
        cpu_percent_p90=('cpu_percent', p90),
        cpu_percent_p95=('cpu_percent', p95),
        cpu_temperature_c_mean=('cpu_temperature_c', 'mean'),
        cpu_temperature_c_std=('cpu_temperature_c', 'std'),
        cpu_temperature_c_p50=('cpu_temperature_c', p50),
        cpu_temperature_c_p90=('cpu_temperature_c', p90),
        cpu_temperature_c_p95=('cpu_temperature_c', p95),
        cpu_frequency_khz_mean=('cpu_frequency_khz', 'mean'),
        cpu_frequency_khz_std=('cpu_frequency_khz', 'std'),
        cpu_frequency_khz_p50=('cpu_frequency_khz', p50),
        cpu_frequency_khz_p90=('cpu_frequency_khz', p90),
        cpu_frequency_khz_p95=('cpu_frequency_khz', p95)
    ).reset_index()

    return grouped

def build_overall_table(metrics_statistics, events_statistics):
    # Use the system metrics because they represent total CPU and RAM usage.
    system_metrics = metrics_statistics[
        metrics_statistics['application'] == 'system'
    ].copy()

    metrics_by_method = system_metrics.groupby('method').agg(
        cpu_average=('cpu_percent_mean', 'mean'),
        cpu_std_dev=('cpu_percent_mean', 'std'),
        ram_average=('memory_mb_mean', 'mean'),
        ram_std_dev=('memory_mb_mean', 'std')
    )

    processing_by_method = events_statistics.groupby('method').agg(
        processing_average=('total_time_mean', 'mean'),
        processing_std_dev=('total_time_mean', 'std')
    )

    values = pd.DataFrame({
        'Métrica': ['Percentual de CPU', 'Memória RAM (MB)', 'Tempo de processamento (ms)'],
        ('Média', 'Nativo'): [
            metrics_by_method.loc['standalone', 'cpu_average'],
            metrics_by_method.loc['standalone', 'ram_average'],
            processing_by_method.loc['standalone', 'processing_average']
        ],
        ('Desvio Padrão', 'Nativo'): [
            metrics_by_method.loc['standalone', 'cpu_std_dev'],
            metrics_by_method.loc['standalone', 'ram_std_dev'],
            processing_by_method.loc['standalone', 'processing_std_dev']
        ],
        ('Média', 'Docker'): [
            metrics_by_method.loc['container', 'cpu_average'],
            metrics_by_method.loc['container', 'ram_average'],
            processing_by_method.loc['container', 'processing_average']
        ],
        ('Desvio Padrão', 'Docker'): [
            metrics_by_method.loc['container', 'cpu_std_dev'],
            metrics_by_method.loc['container', 'ram_std_dev'],
            processing_by_method.loc['container', 'processing_std_dev']
        ]
    })

    values.columns = pd.MultiIndex.from_tuples([
        ('Métrica', ''),
        ('Média', 'Nativo'),
        ('Desvio Padrão', 'Nativo'),
        ('Média', 'Docker'),
        ('Desvio Padrão', 'Docker')
    ])

    values[('Overhead absoluto', '')] = (
        values[('Média', 'Docker')] - values[('Média', 'Nativo')]
    )
    values[('Overhead relativo (%)', '')] = (
        values[('Overhead absoluto', '')]
        / values[('Média', 'Nativo')]
        * 100
    )

    values.columns = [
        'Métrica',
        'Média',
        'Desvio Padrão',
        'Média',
        'Desvio Padrão',
        'Overhead absoluto',
        'Overhead relativo (%)'
    ]
    return values

def build_application_table(metrics_statistics):
    # Filter out the system metrics
    application_metrics = metrics_statistics[
        metrics_statistics['application'] != 'system'
    ].copy()

    # Group by method and application, then calculate the required statistics
    grouped = application_metrics.groupby(['method', 'application']).agg(
        cpu_average=('cpu_percent_mean', 'mean'),
        ram_average=('memory_mb_mean', 'mean')
    )
    applications = [
        'camera', 'classifier', 'camera_shim', 'classifier_shim',
        'dockerd', 'containerd'
    ]
    grouped = grouped.reindex(
        pd.MultiIndex.from_product(
            [['standalone', 'container'], applications],
            names=['method', 'application']
        )
    )

    values = pd.DataFrame({
        'Aplicação': ['Simulador de Câmera', 'Classificador', 'Simulador de Câmera (shim)', 'Classificador (shim)', 'Dockerd', 'containerd'],
        ('Uso de CPU (%)', 'Nativo'): [
            grouped.loc[('standalone', 'camera'), 'cpu_average'],
            grouped.loc[('standalone', 'classifier'), 'cpu_average'],
            grouped.loc[('standalone', 'camera_shim'), 'cpu_average'],
            grouped.loc[('standalone', 'classifier_shim'), 'cpu_average'],
            grouped.loc[('standalone', 'dockerd'), 'cpu_average'],
            grouped.loc[('standalone', 'containerd'), 'cpu_average'],
        ],
        ('Uso de RAM (MB)', 'Nativo'): [
            grouped.loc[('standalone', 'camera'), 'ram_average'],
            grouped.loc[('standalone', 'classifier'), 'ram_average'],
            grouped.loc[('standalone', 'camera_shim'), 'ram_average'],
            grouped.loc[('standalone', 'classifier_shim'), 'ram_average'],
            grouped.loc[('standalone', 'dockerd'), 'ram_average'],
            grouped.loc[('standalone', 'containerd'), 'ram_average']
        ],
        ('Uso de CPU (%)', 'Docker'): [
            grouped.loc[('container', 'camera'), 'cpu_average'],
            grouped.loc[('container', 'classifier'), 'cpu_average'],
            grouped.loc[('container', 'camera_shim'), 'cpu_average'],
            grouped.loc[('container', 'classifier_shim'), 'cpu_average'],
            grouped.loc[('container', 'dockerd'), 'cpu_average'],
            grouped.loc[('container', 'containerd'), 'cpu_average'],
        ],
        ('Uso de RAM (MB)', 'Docker'): [
            grouped.loc[('container', 'camera'), 'ram_average'],
            grouped.loc[('container', 'classifier'), 'ram_average'],
            grouped.loc[('container', 'camera_shim'), 'ram_average'],
            grouped.loc[('container', 'classifier_shim'), 'ram_average'],
            grouped.loc[('container', 'dockerd'), 'ram_average'],
            grouped.loc[('container', 'containerd'), 'ram_average']
        ],
    })

    values.columns = pd.MultiIndex.from_tuples([
        ('Aplicação', ''),
        ('Uso de CPU (%)', 'Nativo'),
        ('Uso de RAM (MB)', 'Nativo'),
        ('Uso de CPU (%)', 'Docker'),
        ('Uso de RAM (MB)', 'Docker')
    ])

    return values

def calculate_p_value(df_metrics, df_events):
    system_metrics = df_metrics[
        df_metrics['application'] == 'system'
    ]

    comparisons = {
        'Percentual de CPU': (
            system_metrics.loc[
                system_metrics['method'] == 'standalone',
                'cpu_percent_mean'
            ],
            system_metrics.loc[
                system_metrics['method'] == 'container',
                'cpu_percent_mean'
            ]
        ),
        'Memórica RAM': (
            system_metrics.loc[
                system_metrics['method'] == 'standalone',
                'memory_mb_mean'
            ],
            system_metrics.loc[
                system_metrics['method'] == 'container',
                'memory_mb_mean'
            ]
        ),
        'Tempo de processamento (ms)': (
            df_events.loc[
                df_events['method'] == 'standalone',
                'total_time_mean'
            ],
            df_events.loc[
                df_events['method'] == 'container',
                'total_time_mean'
            ]
        )
    }

    p_values = []
    for metric, (standalone, container) in comparisons.items():
        # Limpeza dos dados
        data_std = standalone.dropna()
        data_cnt = container.dropna()

        # 1. Testa a normalidade dos dois grupos usando Shapiro-Wilk
        _, p_norm_std = shapiro(data_std)
        _, p_norm_cnt = shapiro(data_cnt)

        # A premissa do Teste t exige que AMBOS os grupos sejam normais
        if p_norm_std > 0.05 and p_norm_cnt > 0.05:
            # Grupos normais -> Teste paramétrico
            teste_usado = 'Teste t (Welch)'
            _, p_value = ttest_ind(data_std, data_cnt, equal_var=False)
        else:
            # Pelo menos um grupo não é normal -> Teste não-paramétrico
            teste_usado = 'Mann-Whitney'
            _, p_value = mannwhitneyu(data_std, data_cnt, alternative='two-sided')

        p_values.append({
            'Métrica': metric,
            'p-valor': p_value
        })

    return pd.DataFrame(p_values)

def generate_memory_graph(df_metrics, output_path, time_bin_seconds=1.0):
    memory_data = df_metrics[
        df_metrics['application'] == 'system'
    ][['timestamp', 'memory_mb', 'method', 'run']].copy()
    memory_data['time_bin'] = (
        memory_data['timestamp'] // time_bin_seconds
    ) * time_bin_seconds
    memory_data = memory_data.groupby(
        ['method', 'run', 'time_bin'],
        as_index=False
    )['memory_mb'].mean()
    memory_data['Método'] = memory_data['method'].replace({
        'container': 'Docker',
        'standalone': 'Standalone'
    })

    figure, axis = plt.subplots(figsize=(10, 6))
    sns.lineplot(
        data=memory_data,
        x='time_bin',
        y='memory_mb',
        hue='Método',
        errorbar=('ci', 95),
        estimator='mean',
        ax=axis
    )
    axis.set_xlabel('Tempo de execução (s)')
    axis.set_ylabel('Uso de RAM (MB)')
    axis.set_xlim(left=0)
    axis.set_ylim(bottom=0)
    axis.grid(True)
    figure.tight_layout()
    figure.savefig(output_path, dpi=300)
    plt.close(figure)

    return output_path

def generate_cpu_graph(df_metrics, output_path, time_bin_seconds=1.0):
    cpu_data = df_metrics[
        df_metrics['application'] == 'system'
    ][['timestamp', 'cpu_percent', 'method', 'run']].copy()
    cpu_data['time_bin'] = (
        cpu_data['timestamp'] // time_bin_seconds
    ) * time_bin_seconds
    cpu_data = cpu_data.groupby(
        ['method', 'run', 'time_bin'],
        as_index=False
    )['cpu_percent'].mean()
    cpu_data['Método'] = cpu_data['method'].replace({
        'container': 'Docker',
        'standalone': 'Standalone'
    })

    figure, axis = plt.subplots(figsize=(10, 6))
    sns.lineplot(
        data=cpu_data,
        x='time_bin',
        y='cpu_percent',
        hue='Método',
        errorbar=('ci', 95),
        estimator='mean',
        ax=axis
    )
    axis.set_xlabel('Tempo de execução (s)')
    axis.set_ylabel('Uso de CPU (%)')
    axis.set_xlim(left=0)
    axis.set_ylim(bottom=0)
    axis.grid(True)
    figure.tight_layout()
    figure.savefig(output_path, dpi=300)
    plt.close(figure)

    return output_path

def export_tables_to_markdown(tables, output_filename):
    with output_filename.open('w', encoding='utf-8') as markdown_file:
        markdown_file.write('# Tabelas de estatísticas\n\n')

        for title, table in tables.items():
            markdown_file.write(f'## {title}\n\n')
            markdown_file.write(
                table.to_markdown(index=False, floatfmt='.2f')
            )
            markdown_file.write('\n\n')

def generate_cpu_temp_graph(df_metrics, output_path, time_bin_seconds=1.0):
    cpu_data = df_metrics[
        df_metrics['application'] == 'system'
    ][['timestamp', 'cpu_temperature_c', 'method', 'run']].copy()
    cpu_data['time_bin'] = (
        cpu_data['timestamp'] // time_bin_seconds
    ) * time_bin_seconds
    cpu_data = cpu_data.groupby(
        ['method', 'run', 'time_bin'],
        as_index=False
    )['cpu_temperature_c'].mean()
    cpu_data['Método'] = cpu_data['method'].replace({
        'container': 'Docker',
        'standalone': 'Standalone'
    })

    figure, axis = plt.subplots(figsize=(10, 6))
    sns.lineplot(
        data=cpu_data,
        x='time_bin',
        y='cpu_temperature_c',
        hue='Método',
        errorbar=('pi', 95),
        estimator='mean',
        ax=axis
    )
    axis.set_xlabel('Tempo de execução (s)')
    axis.set_ylabel('Temperatura da CPU (°C)')
    axis.set_xlim(left=0)
    axis.set_ylim(bottom=0)
    axis.grid(True)
    figure.tight_layout()
    figure.savefig(output_path, dpi=300)
    plt.close(figure)

    return output_path

def generate_cpu_freq_graph(df_metrics, output_path, time_bin_seconds=1.0):
    cpu_data = df_metrics[
        df_metrics['application'] == 'system'
    ][['timestamp', 'cpu_frequency_khz', 'method', 'run']].copy()
    cpu_data['time_bin'] = (
        cpu_data['timestamp'] // time_bin_seconds
    ) * time_bin_seconds
    cpu_data = cpu_data.groupby(
        ['method', 'run', 'time_bin'],
        as_index=False
    )['cpu_frequency_khz'].mean()
    cpu_data['Método'] = cpu_data['method'].replace({
        'container': 'Docker',
        'standalone': 'Standalone'
    })

    figure, axis = plt.subplots(figsize=(10, 6))
    sns.lineplot(
        data=cpu_data,
        x='time_bin',
        y='cpu_frequency_khz',
        hue='Método',
        errorbar=('pi', 95),
        estimator='mean',
        ax=axis
    )
    axis.set_xlabel('Tempo de execução (s)')
    axis.set_ylabel('Frequência da CPU (kHz)')
    axis.set_xlim(left=0)
    axis.set_ylim(bottom=0)
    axis.grid(True)
    figure.tight_layout()
    figure.savefig(output_path, dpi=300)
    plt.close(figure)

    return output_path

def generate_process_time_graph(df_events, output_path, time_bin_seconds=0.1):
    process_data = df_events[['timestamp', 'total_time_ms', 'method', 'run', 'image_id']].copy()
    process_data['time_bin'] = (
        process_data['timestamp'] // time_bin_seconds
    ) * time_bin_seconds    
    process_data = process_data.groupby(
        ['method', 'run', 'time_bin'],
        as_index=False
    )['total_time_ms'].mean()
    
    process_data['Método'] = process_data['method'].replace({
        'container': 'Docker',
        'standalone': 'Standalone'
    })

    figure, axis = plt.subplots(figsize=(10, 6))
    sns.lineplot(
        data=process_data,
        x='time_bin',
        y='total_time_ms',
        hue='Método',
        errorbar=('pi', 95),
        estimator='mean',
        ax=axis
    )
    axis.set_xlabel('Tempo de execução (s)')
    axis.set_ylabel('Tempo total (ms)')
    axis.set_xlim(left=0)
    axis.set_ylim(bottom=0)
    axis.grid(True)
    figure.tight_layout()
    figure.savefig(output_path, dpi=300)
    plt.close(figure)

    return output_path

def generate_application_graph(df_metrics, method, metric, output_path, time_bin_seconds=1.0):
    method_labels = {
        'standalone': 'Nativo',
        'container': 'Docker'
    }
    application_labels = {
        'camera': 'Câmera',
        'classifier': 'Classificador',
        'camera_shim': 'Câmera (shim)',
        'classifier_shim': 'Classificador (shim)',
        'dockerd': 'Dockerd',
        'containerd': 'containerd'
    }
    metric_labels = {
        'cpu_percent': 'Uso de CPU (%)',
        'memory_mb': 'Uso de RAM (MB)'
    }
    metric_title = {
        'cpu_percent': 'CPU',
        'memory_mb': 'RAM'
    }

    plot_data = df_metrics[
        (df_metrics['method'] == method) &
        (df_metrics['application'] != 'system')
    ][['timestamp', 'run', 'application', metric]].copy()

    plot_data['time_bin'] = (
        plot_data['timestamp'] // time_bin_seconds
    ) * time_bin_seconds


    plot_data = plot_data.groupby(
        ['application', 'run', 'time_bin'],
        as_index=False
    )[metric].mean()

    app_order = ['camera', 'classifier', 'camera_shim', 'classifier_shim', 'dockerd', 'containerd']
    plot_data['application'] = plot_data['application'].map(application_labels)
    plot_data = plot_data[plot_data['application'].notna()].copy()
    plot_data['run'] = plot_data['run'].astype(int)

    hue_order = [
        application_labels[app]
        for app in app_order
        if app in df_metrics['application'].unique()
    ]

    figure, axis = plt.subplots(figsize=(10, 6))
    sns.lineplot(
        data=plot_data,
        x='time_bin',
        y=metric,
        hue='application',
        errorbar=('ci', 95),
        estimator='mean',
        ax=axis
    )
    axis.set_xlabel('Tempo de execução (s)')
    axis.set_ylabel(metric_labels[metric])
    axis.set_xlim(left=0)
    axis.set_ylim(bottom=0)
    axis.grid(True)

    legend = axis.get_legend()
    if legend is not None:
        legend.set_title('Aplicação')
        for text in legend.get_texts():
            text.set_fontsize(10)

    figure.tight_layout()
    figure.savefig(output_path, dpi=300)
    plt.close(figure)

    return output_path

def generate_application_boxplot(df_metrics, method, metric, output_path):

    method_labels = {
        'standalone': 'Nativo',
        'container': 'Docker'
    }
    application_labels = {
        'camera': 'Câmera',
        'classifier': 'Classificador',
        'camera_shim': 'Câmera (shim)',
        'classifier_shim': 'Classificador (shim)',
        'dockerd': 'Dockerd',
        'containerd': 'containerd'
    }
    metric_labels = {
        'cpu_percent': 'Uso de CPU (%)',
        'memory_mb': 'Uso de RAM (MB)'
    }
    metric_title = {
        'cpu_percent': 'CPU',
        'memory_mb': 'RAM'
    }

    plot_data = df_metrics[
        (df_metrics['method'] == method) &
        (df_metrics['application'] != 'system')
    ][['run', 'application', metric]].copy()

    if plot_data.empty:
        raise ValueError(f"Nenhum dado encontrado para o método '{method}'")

    app_order = ['camera', 'classifier', 'camera_shim', 'classifier_shim', 'dockerd', 'containerd']
    plot_data['application'] = plot_data['application'].map(application_labels)
    plot_data = plot_data[plot_data['application'].notna()].copy()
    plot_data['run'] = plot_data['run'].astype(int)

    hue_order = [
        application_labels[app]
        for app in app_order
        if app in df_metrics['application'].unique()
    ]

    figure, axis = plt.subplots(figsize=(12, 7))
    sns.boxplot(
        data=plot_data,
        x='run',
        y=metric,
        hue='application',
        order=sorted(plot_data['run'].unique()),
        hue_order=hue_order,
        dodge=True,
        ax=axis,
        width=0.5,
        palette='Set2'
    )

    axis.set_xlabel('Execução')
    axis.set_ylabel(metric_labels[metric])
    axis.set_title(f"Consumo de {metric_title[metric]} - {method_labels[method]}")
    axis.grid(True, axis='y', linestyle='--', alpha=0.5)
    axis.tick_params(axis='x', rotation=0)

    legend = axis.get_legend()
    if legend is not None:
        legend.set_title('Aplicação')
        for text in legend.get_texts():
            text.set_fontsize(10)

    figure.tight_layout()
    figure.savefig(output_path, dpi=300)
    plt.close(figure)

    return output_path

def main():
    df_events = load_events_file(base_path)
    df_metrics = load_metrics_file(base_path)
    
    events_statistics = calculate_event_statistics(df_events)
    metrics_statistics = calculate_metrics_statistics(df_metrics)

    # # Export to CSV using ';' as column separator and ',' as decimal separator
    # output_filename = Path.joinpath(output_path, "events_statistics.csv")
    # events_statistics.to_csv(output_filename, sep=';', decimal=',', index=False, float_format='%.2f')

    # # Export to CSV using ';' as column separator and ',' as decimal separator
    # output_filename = Path.joinpath(output_path, "metrics_statistics.csv")
    # metrics_statistics.to_csv(output_filename, sep=';', decimal=',', index=False, float_format='%.2f')

    # # Export to CSV using ';' as column separator and ',' as decimal separator
    # output_filename = Path.joinpath(output_path, "consolidated_metrics.csv")
    # df_metrics.to_csv(output_filename, sep=';', decimal=',', index=False, float_format='%.2f')

    # # Export to CSV using ';' as column separator and ',' as decimal separator
    # output_filename = Path.joinpath(output_path, "consolidated_events.csv")
    # df_events.to_csv(output_filename, sep=';', decimal=',', index=False, float_format='%.2f')

    overall_table = build_overall_table(metrics_statistics, events_statistics)
    # output_filename = Path.joinpath(output_path, "1_overall_statistics.csv")
    # overall_table.to_csv(output_filename, sep=';', decimal=',', index=False, float_format='%.2f')

    application_table = build_application_table(metrics_statistics)
    # output_filename = Path.joinpath(output_path, "2_application_statistics.csv")
    # application_table.to_csv(output_filename, sep=';', decimal=',', index=False, float_format='%.2f')

    p_values = calculate_p_value(metrics_statistics, events_statistics)
    # output_filename = Path.joinpath(output_path, "3_p_values.csv")
    # p_values.to_csv(output_filename, sep=';', decimal=',', index=False, float_format='%.5e')

    tables = {
        'Estatísticas gerais': overall_table,
        'Estatísticas por aplicação': application_table,
        'Valores de p': p_values
    }
    output_filename = Path.joinpath(output_path, 'tables.md')
    export_tables_to_markdown(tables, output_filename)

    output_filename = Path.joinpath(output_path, "10_memory_graph.png")
    generate_memory_graph(df_metrics, output_filename)

    output_filename = Path.joinpath(output_path, "11_cpu_graph.png")
    generate_cpu_graph(df_metrics, output_filename)

    # output_filename = Path.joinpath(output_path, "12_cpu_frequency_graph.png")
    # generate_cpu_freq_graph(df_metrics, output_filename)

    output_filename = Path.joinpath(output_path, "12_process_time_graph.png")
    generate_process_time_graph(df_events, output_filename)

    output_filename = Path.joinpath(output_path, "13_cpu_temperature_graph.png")
    generate_cpu_temp_graph(df_metrics, output_filename)

    output_filename = Path.joinpath(output_path, "6_app_standalone_cpu.png")
    generate_application_graph(df_metrics, "standalone", "cpu_percent", output_filename)

    output_filename = Path.joinpath(output_path, "7_app_container_cpu.png")
    generate_application_graph(df_metrics, "container", "cpu_percent", output_filename)

    output_filename = Path.joinpath(output_path, "8_app_standalone_ram.png")
    generate_application_graph(df_metrics, "standalone", "memory_mb", output_filename)

    output_filename = Path.joinpath(output_path, "9_app_container_ram.png")
    generate_application_graph(df_metrics, "container", "memory_mb", output_filename)

if __name__ == "__main__":
    main()