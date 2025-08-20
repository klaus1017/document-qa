# =============================================================================
# 分析功能函数
# =============================================================================

def calculate_monthly_summary(df):
    """按月计算汇总数据 - 基于分开查询的逻辑"""
    if df.empty:
        return pd.DataFrame(), pd.DataFrame()
    
    df_work = df.copy()
    
    # 物料级别的汇总数据（已经包含单耗）
    monthly_material_summary = df_work.copy()
    
    # 部门级别的汇总数据
    monthly_dept_summary = df_work.groupby(['YEAR_MONTH', 'DEPT_CODE_STD', 'DEPT_NAME_STD']).agg({
        'TOTAL_COST': 'sum',     # 部门总成本
        'WPNL_SIZE': 'first',    # 部门产出（所有行都相同）
        'QUAN': 'sum',           # 部门总数量
        'INV': 'nunique'         # 部门物料种类数
    }).reset_index()
    
    # 计算部门单耗
    monthly_dept_summary['UNIT_CONSUMPTION'] = monthly_dept_summary['TOTAL_COST'] / monthly_dept_summary['WPNL_SIZE']
    monthly_dept_summary['UNIT_CONSUMPTION'] = monthly_dept_summary['UNIT_CONSUMPTION'].replace([np.inf, -np.inf], 0).fillna(0)
    
    return monthly_material_summary, monthly_dept_summary

def calculate_comprehensive_variance_analysis(df):
    """根据新的业务逻辑进行全面的变差分析"""
    if df.empty:
        return {}
    
    results = {}
    
    # 1. 单耗变差分析（与上月对比）
    if 'DATE' in df.columns:
        # 按物料、部门、日期计算日单耗
        daily_data = df.groupby(['INV', 'DEPT_NAME_STD', 'DATE']).agg({
            'TOTAL_COST': 'sum',
            'QUAN': 'sum'
        }).reset_index()
        
        # 获取部门日产出
        dept_daily_output = df.groupby(['DEPT_NAME_STD', 'DATE'])['WPNL_SIZE'].first().reset_index()
        
        # 合并计算日单耗
        daily_merged = daily_data.merge(dept_daily_output, on=['DEPT_NAME_STD', 'DATE'], how='left')
        daily_merged['日单耗'] = (daily_merged['TOTAL_COST'] / daily_merged['WPNL_SIZE']).replace([np.inf, -np.inf], 0).fillna(0)
        
        # 按月汇总计算月单耗
        daily_merged['年月'] = pd.to_datetime(daily_merged['DATE']).dt.to_period('M')
        monthly_unit_data = daily_merged.groupby(['INV', 'DEPT_NAME_STD', '年月']).agg({
            'TOTAL_COST': 'sum',
            'WPNL_SIZE': 'sum'
        }).reset_index()
        monthly_unit_data['月单耗'] = (monthly_unit_data['TOTAL_COST'] / monthly_unit_data['WPNL_SIZE']).replace([np.inf, -np.inf], 0).fillna(0)
        
        # 计算单耗变差（与上月对比）
        monthly_unit_sorted = monthly_unit_data.sort_values(['INV', 'DEPT_NAME_STD', '年月'])
        monthly_unit_sorted['上月单耗'] = monthly_unit_sorted.groupby(['INV', 'DEPT_NAME_STD'])['月单耗'].shift(1)
        monthly_unit_sorted['单耗变差'] = monthly_unit_sorted['月单耗'] - monthly_unit_sorted['上月单耗']
        monthly_unit_sorted['单耗变差百分比'] = ((monthly_unit_sorted['单耗变差'] / monthly_unit_sorted['上月单耗']) * 100).replace([np.inf, -np.inf], np.nan).round(2)
        
        # 筛选最新月份且单耗增加的记录
        latest_month = monthly_unit_sorted['年月'].max()
        unit_variance = monthly_unit_sorted[
            (monthly_unit_sorted['年月'] == latest_month) & 
            (monthly_unit_sorted['单耗变差百分比'].notna()) &
            (monthly_unit_sorted['单耗变差'] > 0)
        ].copy()
        
        # 排序：先按变差绝对值，再按变差百分比绝对值
        unit_variance['变差绝对值'] = unit_variance['单耗变差'].abs()
        unit_variance['百分比绝对值'] = unit_variance['单耗变差百分比'].abs()
        unit_variance = unit_variance.sort_values(['变差绝对值', '百分比绝对值'], ascending=[False, False])
        
        results['单耗变差'] = unit_variance.head(10)
        results['日单耗数据'] = daily_merged
    
    # 2. 耗用量变差分析（与前一天对比）
    if 'DATE' in df.columns:
        daily_qty = df.groupby(['INV', 'DATE'])['QUAN'].sum().reset_index()
        daily_qty_sorted = daily_qty.sort_values(['INV', 'DATE'])
        daily_qty_sorted['前一天数量'] = daily_qty_sorted.groupby('INV')['QUAN'].shift(1)
        daily_qty_sorted['数量变差'] = daily_qty_sorted['QUAN'] - daily_qty_sorted['前一天数量']
        daily_qty_sorted['数量变差百分比'] = ((daily_qty_sorted['数量变差'] / daily_qty_sorted['前一天数量']) * 100).replace([np.inf, -np.inf], np.nan).round(2)
        
        # 筛选最新日期且数量增加的记录
        latest_date = daily_qty_sorted['DATE'].max()
        qty_variance = daily_qty_sorted[
            (daily_qty_sorted['DATE'] == latest_date) & 
            (daily_qty_sorted['数量变差百分比'].notna()) &
            (daily_qty_sorted['数量变差'] > 0)
        ].copy()
        
        # 排序：先按变差绝对值，再按变差百分比绝对值
        qty_variance['变差绝对值'] = qty_variance['数量变差'].abs()
        qty_variance['百分比绝对值'] = qty_variance['数量变差百分比'].abs()
        qty_variance = qty_variance.sort_values(['变差绝对值', '百分比绝对值'], ascending=[False, False])
        
        results['数量变差'] = qty_variance.head(10)
        results['每日数量数据'] = daily_qty_sorted
    
    # 3. 月耗用量变差分析（与上月对比）
    df_copy = df.copy()
    df_copy['年月'] = pd.to_datetime(df_copy['YYYYMM'] + '01', format='%Y%m%d').dt.to_period('M')
    monthly_qty = df_copy.groupby(['INV', '年月'])['QUAN'].sum().reset_index()
    monthly_qty_sorted = monthly_qty.sort_values(['INV', '年月'])
    monthly_qty_sorted['上月数量'] = monthly_qty_sorted.groupby('INV')['QUAN'].shift(1)
    monthly_qty_sorted['月数量变差'] = monthly_qty_sorted['QUAN'] - monthly_qty_sorted['上月数量']
    monthly_qty_sorted['月数量变差百分比'] = ((monthly_qty_sorted['月数量变差'] / monthly_qty_sorted['上月数量']) * 100).replace([np.inf, -np.inf], np.nan).round(2)
    
    # 筛选最新月份且数量增加的记录
    latest_month = monthly_qty_sorted['年月'].max()
    monthly_qty_variance = monthly_qty_sorted[
        (monthly_qty_sorted['年月'] == latest_month) & 
        (monthly_qty_sorted['月数量变差百分比'].notna()) &
        (monthly_qty_sorted['月数量变差'] > 0)
    ].copy()
    
    # 排序：先按变差绝对值，再按变差百分比绝对值
    monthly_qty_variance['变差绝对值'] = monthly_qty_variance['月数量变差'].abs()
    monthly_qty_variance['百分比绝对值'] = monthly_qty_variance['月数量变差百分比'].abs()
    monthly_qty_variance = monthly_qty_variance.sort_values(['变差绝对值', '百分比绝对值'], ascending=[False, False])
    
    results['月数量变差'] = monthly_qty_variance.head(10)
    
    return results

def render_analysis_results(df):
    """渲染分析结果 - 更新版本"""
    if df.empty:
        st.warning("没有数据可供分析")
        return
    
    # 计算汇总数据和变差分析
    monthly_material_summary, monthly_dept_summary = calculate_monthly_summary(df)
    variance_analysis = calculate_comprehensive_variance_analysis(df)
    
    # 显示关键指标
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_cost = df['TOTAL_COST'].sum()
        st.metric("总成本", f"¥{total_cost/10000:.2f}万")
    
    with col2:
        total_quan = df['QUAN'].sum()
        st.metric("总数量", f"{total_quan:,.0f}")
    
    with col3:
        # 由于产出是部门级别的，需要去重计算
        total_wpnl = df.groupby(['DEPT_NAME_STD', 'YYYYMM'])['WPNL_SIZE'].first().sum()
        st.metric("总产出", f"{total_wpnl/10000:.2f}万")
    
    with col4:
        # 计算总体平均单耗
        total_unit_consumption = total_cost / total_wpnl if total_wpnl > 0 else 0
        st.metric("总体平均单耗", f"¥{total_unit_consumption:.2f}")
    
    # 创建标签页 - 根据新的分析框架重新设计
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["数量分析", "部门分析", "物料分析", "单价分析", "月度趋势","AI分析"])
    
    with tab1:
        st.subheader("数量分析 - 每个物料的每日领用量")
        
        # 显示变差最大物料的数量趋势图
        if '数量变差' in variance_analysis and not variance_analysis['数量变差'].empty:
            # 获取变差最大的前10个物料
            top_variance_materials = variance_analysis['数量变差']['INV'].tolist()
            
            if '每日数量数据' in variance_analysis:
                # 筛选变差最大的物料数据用于绘图
                plot_data = variance_analysis['每日数量数据'][
                    variance_analysis['每日数量数据']['INV'].isin(top_variance_materials)
                ]
                
                if not plot_data.empty:
                    # 绘制变差最大物料的每日数量趋势
                    fig_qty_trend = px.line(
                        plot_data,
                        x='DATE',
                        y='QUAN',
                        color='INV',
                        title='数量变差最大的前10个物料每日领用量趋势',
                        labels={'QUAN': '领用量', 'DATE': '日期', 'INV': '物料'}
                    )
                    fig_qty_trend.update_layout(height=500)
                    st.plotly_chart(fig_qty_trend, use_container_width=True)
        
        # 每日耗用量变差前10名明细
        st.subheader("每日耗用量变差前10名明细（较前一天）")
        
        if '数量变差' in variance_analysis and not variance_analysis['数量变差'].empty:
            qty_variance_display = variance_analysis['数量变差'][
                ['INV', 'DATE', 'QUAN', '前一天数量', '数量变差', '数量变差百分比']
            ].copy()
            qty_variance_display.columns = ['物料', '当前日期', '当日数量', '前一天数量', '数量变差', '变差百分比(%)']
            
            # 处理边界情况：当前一天数量为0时显示特殊标记
            qty_variance_display['变差百分比(%)'] = qty_variance_display['变差百分比(%)'].fillna('∞')
            
            try:
                st.dataframe(
                    qty_variance_display.style.format({
                        '当日数量': '{:,.0f}',
                        '前一天数量': '{:,.0f}',
                        '数量变差': '{:+,.0f}',
                        '变差百分比(%)': lambda x: f'{x:+.2f}%' if isinstance(x, (int, float)) else str(x)
                    }),
                    use_container_width=True
                )
            except:
                st.dataframe(qty_variance_display, use_container_width=True)
        else:
            st.info("没有足够的数据进行每日耗用量变差分析")
        
        # 月度耗用量变差前10名明细
        st.subheader("月度耗用量变差前10名明细（较上月）")
        
        if '月数量变差' in variance_analysis and not variance_analysis['月数量变差'].empty:
            monthly_qty_variance_display = variance_analysis['月数量变差'][
                ['INV', '年月', 'QUAN', '上月数量', '月数量变差', '月数量变差百分比']
            ].copy()
            monthly_qty_variance_display.columns = ['物料', '当前月份', '当月数量', '上月数量', '数量变差', '变差百分比(%)']
            
            # 处理边界情况
            monthly_qty_variance_display['变差百分比(%)'] = monthly_qty_variance_display['变差百分比(%)'].fillna('∞')
            
            try:
                st.dataframe(
                    monthly_qty_variance_display.style.format({
                        '当月数量': '{:,.0f}',
                        '上月数量': '{:,.0f}',
                        '数量变差': '{:+,.0f}',
                        '变差百分比(%)': lambda x: f'{x:+.2f}%' if isinstance(x, (int, float)) else str(x)
                    }),
                    use_container_width=True
                )
            except:
                st.dataframe(monthly_qty_variance_display, use_container_width=True)
        else:
            st.info("没有足够的数据进行月度耗用量变差分析")
    
    with tab2:
        st.subheader("部门分析 - 单耗排名")
        
        # 部门单耗排名
        if '日单耗数据' in variance_analysis:
            # 计算各部门内物料的平均单耗排名
            dept_material_unit_consumption = variance_analysis['日单耗数据'].groupby(['DEPT_NAME_STD', 'INV']).agg({
                '日单耗': 'mean',
                'TOTAL_COST': 'sum'
            }).reset_index()
            
            # 选择部门进行分析
            dept_list = dept_material_unit_consumption['DEPT_NAME_STD'].unique()
            selected_dept = st.selectbox("选择部门查看单耗排名：", dept_list)
            
            if selected_dept:
                dept_data = dept_material_unit_consumption[
                    dept_material_unit_consumption['DEPT_NAME_STD'] == selected_dept
                ].sort_values('日单耗', ascending=False)
                
                st.subheader(f"{selected_dept} - 物料单耗排名")
                
                # 显示排名表
                dept_ranking_display = dept_data[['INV', '日单耗', 'TOTAL_COST']].copy()
                dept_ranking_display['总成本'] = dept_ranking_display['TOTAL_COST'] / 10000  # 转换为万元
                dept_ranking_display.columns = ['物料', '平均日单耗', '总成本']
                dept_ranking_display['排名'] = range(1, len(dept_ranking_display) + 1)
                dept_ranking_display = dept_ranking_display[['排名', '物料', '平均日单耗', '总成本']]
                
                try:
                    st.dataframe(
                        dept_ranking_display.style.format({
                            '平均日单耗': '¥{:.2f}',
                            '总成本': '¥{:.2f}万'
                        }),
                        use_container_width=True
                    )
                except:
                    st.dataframe(dept_ranking_display, use_container_width=True)
                
                # 显示该部门的单耗变差
                if '单耗变差' in variance_analysis:
                    dept_unit_variance = variance_analysis['单耗变差'][
                        variance_analysis['单耗变差']['DEPT_NAME_STD'] == selected_dept
                    ]
                    
                    if not dept_unit_variance.empty:
                        st.subheader(f"{selected_dept} - 单耗变差前10名明细（较上月）")
                        
                        dept_variance_display = dept_unit_variance[
                            ['INV', '年月', '月单耗', '上月单耗', '单耗变差', '单耗变差百分比']
                        ].copy()
                        dept_variance_display.columns = ['物料', '当前月份', '本月单耗', '上月单耗', '单耗变差', '变差百分比(%)']
                        
                        # 处理边界情况
                        dept_variance_display['变差百分比(%)'] = dept_variance_display['变差百分比(%)'].fillna('∞')
                        
                        try:
                            st.dataframe(
                                dept_variance_display.style.format({
                                    '本月单耗': '¥{:.2f}',
                                    '上月单耗': '¥{:.2f}',
                                    '单耗变差': '¥{:+.2f}',
                                    '变差百分比(%)': lambda x: f'{x:+.2f}%' if isinstance(x, (int, float)) else str(x)
                                }),
                                use_container_width=True
                            )
                        except:
                            st.dataframe(dept_variance_display, use_container_width=True)
                    else:
                        st.info(f"{selected_dept} 暂无单耗变差数据")
        else:
            st.info("没有足够的数据进行部门单耗排名分析")
    
    with tab3:
        st.subheader("部门成本分析")
        
        if not monthly_dept_summary.empty:
            # 部门成本排名
            dept_ranking = monthly_dept_summary.groupby(['DEPT_CODE_STD', 'DEPT_NAME_STD']).agg({
                'TOTAL_COST': 'sum',
                'WPNL_SIZE': 'sum',
                'INV': 'sum'  # 物料种类总数
            }).reset_index().sort_values('TOTAL_COST', ascending=False)
            
            # 计算部门单耗
            dept_ranking['UNIT_CONSUMPTION'] = dept_ranking['TOTAL_COST'] / dept_ranking['WPNL_SIZE']
            dept_ranking['UNIT_CONSUMPTION'] = dept_ranking['UNIT_CONSUMPTION'].fillna(0)
            
            # 添加单耗排名
            dept_unit_ranking = dept_ranking.sort_values('UNIT_CONSUMPTION', ascending=False)
            
            col1, col2 = st.columns(2)
            
            with col1:
                # 部门成本排名图
                fig_cost = px.bar(dept_ranking.head(10), 
                       x='DEPT_NAME_STD', 
                       y='TOTAL_COST',
                       title="部门成本排名 (前10名)")
                fig_cost.update_xaxes(tickangle=45)
                st.plotly_chart(fig_cost, use_container_width=True)
            
            with col2:
                # 部门单耗排名图
                fig_unit = px.bar(dept_unit_ranking.head(10), 
                           x='DEPT_NAME_STD', 
                           y='UNIT_CONSUMPTION',
                           title="部门单耗排名 (前10名)",
                           color='UNIT_CONSUMPTION',
                           color_continuous_scale='Reds')
                fig_unit.update_xaxes(tickangle=45)
                st.plotly_chart(fig_unit, use_container_width=True)
            
            # 部门详细表格
            st.subheader("部门汇总数据")
            
            # 检查必要的列是否存在
            required_cols = ['DEPT_NAME_STD', 'TOTAL_COST', 'WPNL_SIZE', 'INV', 'UNIT_CONSUMPTION']
            if all(col in dept_ranking.columns for col in required_cols):
                display_dept_df = dept_ranking[required_cols].copy()
                display_dept_df['TOTAL_COST'] = display_dept_df['TOTAL_COST'] / 10000  # 转换为万元
                display_dept_df['WPNL_SIZE'] = display_dept_df['WPNL_SIZE'] / 10000  # 转换为万
                display_dept_df.columns = ['部门名称', '总成本', '产出', '物料种类数', '部门单耗']
            else:
                st.error(f"数据结构异常，缺少必要的列。现有列：{list(dept_ranking.columns)}")
                display_dept_df = pd.DataFrame()
            
            try:
                st.dataframe(
                    display_dept_df.style.format({
                        '总成本': '¥{:.2f}万',
                        '产出': '{:.2f}万',
                        '物料种类数': '{:,.0f}',
                        '部门单耗': '¥{:.2f}'
                    }),
                    use_container_width=True
                )
            except Exception:
                st.dataframe(display_dept_df, use_container_width=True)
                
            # 单耗排名表
            st.subheader("部门单耗排名")
            required_ranking_cols = ['DEPT_NAME_STD', 'UNIT_CONSUMPTION', 'TOTAL_COST', 'WPNL_SIZE']
            if all(col in dept_unit_ranking.columns for col in required_ranking_cols):
                display_unit_ranking_df = dept_unit_ranking[required_ranking_cols].copy()
                display_unit_ranking_df['TOTAL_COST'] = display_unit_ranking_df['TOTAL_COST'] / 10000  # 转换为万元
                display_unit_ranking_df['WPNL_SIZE'] = display_unit_ranking_df['WPNL_SIZE'] / 10000  # 转换为万
                display_unit_ranking_df.columns = ['部门名称', '单耗', '总成本', '产出']
                display_unit_ranking_df['排名'] = range(1, len(display_unit_ranking_df) + 1)
                display_unit_ranking_df = display_unit_ranking_df[['排名', '部门名称', '单耗', '总成本', '产出']]
            else:
                st.error(f"单耗排名数据结构异常，缺少必要的列。现有列：{list(dept_unit_ranking.columns)}")
                display_unit_ranking_df = pd.DataFrame()
            
            try:
                st.dataframe(
                    display_unit_ranking_df.style.format({
                        '单耗': '¥{:.2f}',
                        '总成本': '¥{:.2f}万',
                        '产出': '{:.2f}万'
                    }),
                    use_container_width=True
                )
            except Exception:
                st.dataframe(display_unit_ranking_df, use_container_width=True)