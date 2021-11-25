var DateTime = luxon.DateTime;

let currencyCtx = {
    startDate: null,
    endDate: null,
    granularity: 60,
    baseCurrency: null,
    options: [],
    chart: null,
    activeCurrencies: [],
    data: [],
    graphedType: 'open_rate',
}

Date.prototype.addHours = function (h) {
    this.setTime(this.getTime() + (h * 60 * 60 * 1000))
    return this
}

Date.prototype.addDays = function (d) {
    this.setDate(this.getDate() + 1)
    return this
}

Date.prototype.deepCopy = function () {
    return new Date(this.valueOf())
}

$(document).ready(function () {

    // setup start date picker
    let startDatePicker = $('#startDatePicker')
    startDatePicker.datepicker({
        format: 'yyyy-mm-dd',
        container: $('#startPickerContainer'),
        todayHighlight: true,
        autoclose: true,
    })
    startDatePicker.on('change', () => {
        currencyCtx.startDate = $('#startDatePicker').val()
    })

    // setup end date picker
    let endDatePicker = $('#endDatePicker')
    endDatePicker.datepicker({
        format: 'yyyy-mm-dd',
        container: $('#endPickerContainer'),
        todayHighlight: true,
        autoclose: true,
    })
    endDatePicker.on('change', () => {
        currencyCtx.endDate = $('#endDatePicker').val()
    })

    let title = {
        display: true,
        text: 'Crypto Data'
    }
    let data = []
    let scales = {
        y: {
            type: 'linear',
            display: true,
            position: 'left',
        },
        y1: {
            type: 'linear',
            display: true,
            position: 'right',

            // grid line settings
            grid: {
                drawOnChartArea: false, // only want the grid lines for one axis to show up
            },
        },
    }
    let config = {
        type: 'line',
        data,
        options: {
            responsive: true,
            interaction: {
                mode: 'index',
                intersect: false,
            },
            parsing: {
                xAxisKey: 'timestamp',
                yAxisKey: 'nested.value'
            },
            tooltips: {
                mode: 'index',
                intersect: false
            },
            hover: {
                mode: 'index',
                intersect: false
            },
            stacked: false,
            plugins: {
                title,
            },
            scales,
        },
    }
    let ctx = $('#lineChart')
    currencyCtx.chart = new Chart(ctx, config)
})


function updateGranularity() {
    currencyCtx.granularity = $('#granularitySelectPicker').val()
}

function selectColor(number) {
    const hue = number * 137.508; // use golden angle approximation
    return `hsl(${hue},50%,75%)`
}

function retrieveRun() {
    if (DateTime.fromISO(currencyCtx.startDate) > DateTime.fromISO(currencyCtx.endDate)) {
        console.error('bad dates')
        return
    }
    $('#retrieveRun').prop('disabled', true)
    $.get({
        url: '/currency/range',
        headers: {
            startDate: currencyCtx.startDate,
            endDate: currencyCtx.endDate,
            granularity: currencyCtx.granularity,
            baseCurrency: currencyCtx.baseCurrency,
            currencies: currencyCtx.options.join(','),
        },
    }, resp => {
        currencyCtx.data = resp.data
        redrawGraph()
    })
}

function redrawGraph(
    graphData = currencyCtx.data,
    startDate = currencyCtx.startDate,
    endDate = currencyCtx.endDate,
    baseCurrency = currencyCtx.baseCurrency) {
    // Object.entries
    let labels = []
    let dateIter = DateTime.fromISO(startDate)
    let endIter = DateTime.fromISO(endDate)
    let numDays = ((endIter - dateIter) / 1000) / 86400
    let iterJump = 'day'
    if (numDays < 3) {
        iterJump = 'hour'
    }
    while (dateIter <= endIter) {
        labels.push(dateIter)
        if (iterJump == 'hour') {
            dateIter = dateIter.plus({ hours: 1 })
        } else if (iterJump == 'day') {
            dateIter = dateIter.plus({ days: 1 })
        } else {
            console.error('bad iterJump')
        }
    }
    let count = 0
    let yLabel, y1Label, yAxisID
    let datasets = graphData.filter((currencyInfo) => {
        let currency = currencyInfo.currency
        if (!currencyCtx.activeCurrencies.includes(currency) || currency == baseCurrency) {
            return false
        }
        if (count > 2) {
            return false
        }
        count++
        return true
    }).map((currencyInfo, idx) => {
        let currency = currencyInfo.currency
        let rates = currencyInfo.rates
        let rateTypes = ['low_rate', 'high_rate', 'open_rate', 'close_rate', 'volume']
        if (idx != 0) {
            yAxisID = 'y1'
            y1Label = `${currencyInfo.currency} value [${baseCurrency}]`
        } else {
            yAxisID = 'y'
            yLabel = `${currencyInfo.currency} value [${baseCurrency}]`
        }
        return {
            data: rates.map(rate => {
                for (let rateType of rateTypes) {
                    rate[rateType] = parseFloat(rate[rateType])
                }
                rate.timestamp = DateTime.fromISO(rate.timestamp)
                return rate
            }),
            label: `${currency}`,
            borderColor: selectColor(idx),
            fill: false,
            yAxisID,
        }
    })
    let data = {
        labels,
        datasets,
    }
    let scales = {
        x: {
            type: 'time'
        },
        y: {
            type: 'linear',
            display: true,
            position: 'left',
            scaleLabel: {
                display: true,
                labelString: yLabel,
            },
        },
        y1: {
            type: 'linear',
            display: true,
            position: 'right',
            scaleLabel: {
                display: true,
                labelString: y1Label,
            },
            // grid line settings
            grid: {
                drawOnChartArea: false, // only want the grid lines for one axis to show up
            },
        },
    }
    let title = {
        display: true,
        text: 'Crypto Data'
    }
    let config = {
        type: 'line',
        data,
        options: {
            responsive: true,
            interaction: {
                mode: 'index',
                intersect: false,
            },
            parsing: {
                xAxisKey: 'timestamp',
                yAxisKey: currencyCtx.graphedType
            },
            tooltips: {
                mode: 'index',
                intersect: false
            },
            hover: {
                mode: 'index',
                intersect: false
            },
            stacked: false,
            plugins: {
                title,
            },
            scales,
        },
    }
    let ctx = $('#lineChart')
    currencyCtx.chart.destroy()
    currencyCtx.chart = new Chart(ctx, config)
    $('#retrieveRun').prop('disabled', false)
}

function runCollect() {
    $('#collectRun').prop('disabled', true)
    $.get({
        url: '/currency/target',
        headers: {
            startDate: currencyCtx.startDate,
            endDate: currencyCtx.endDate,
            granularity: currencyCtx.granularity,
            baseCurrency: currencyCtx.baseCurrency,
            currencies: currencyCtx.options.join(','),
        },
    }, resp => {
        console.log(resp.data)
        $('#collectRun').prop('disabled', false)
    })
}

function activeCurrencyChange() {
    currencyCtx.activeCurrencies = $('#activeCurrencySelector').val()
}

function baseCurrencyChange() {
    currencyCtx.baseCurrency = $('#currencyBaseSelector').val()
}

function currencySelectorChange() {
    // update base currency selector
    currencyCtx.options = $('#currencySelectPicker').val()
    if (currencyCtx.options) {
        let currencyOptions = currencyCtx.options.map(option => {
            return `<option>${option}</option>`
        }).join()
        let newSelect = `<select id="currencyBaseSelector" title="Base Currency (x-axis)" onchange="baseCurrencyChange()" class="selectpicker ma1" data-live-search="true">${currencyOptions}</select>`
        let basePicker = $('#currencyBasePicker')
        basePicker.empty()
        basePicker.append(newSelect)
        let baseSelector = $('#currencyBaseSelector')
        baseSelector.selectpicker({})
        newSelect = `<select id="activeCurrencySelector" title="Active Currencies (y-axis)" onchange="activeCurrencyChange()" class="selectpicker ma1" multiple data-live-search="true">${currencyOptions}</select>`
        let activePicker = $('#activeCurrencyPicker')
        activePicker.empty()
        activePicker.append(newSelect)
        let activeSelector = $('#activeCurrencySelector')
        activeSelector.selectpicker({})
    }
}

function refreshData() {
    $('button#refreshButton').prop('disabled', true)
    $.get('/currency/refresh', resp => {
        $('button#refreshButton').prop('disabled', false)
    })
}